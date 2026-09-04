"""Ticket-Approv-Agent HTTP 服务：实现 AgentGate Invoke 契约。

契约要点（对应 agentgate/src/agentgate/run/targets/http.py）：
- POST /invoke：请求/响应均为 JSON（Content-Type 必须含 json）
- 响应 200 且必含 output 与 final_state；trace_id 建议返回（32 位 hex）
- 头部 traceparent / Idempotency-Key / X-AgentGate-* 照收不拒
- 遥测通过 OTLP 单独上报（telemetry.py），不在响应中携带
"""

from __future__ import annotations

import logging
import os
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from pydantic import BaseModel

from chain import TicketApprovAgent
from telemetry import export_trace

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("ticket_agent")

app = FastAPI(title="Ticket-Approv-Agent")

agent = TicketApprovAgent()


class InvokeResponse(BaseModel):
    invocation_id: str
    external_execution_id: str
    output: dict[str, Any]
    final_state: dict[str, Any]
    trace_id: str


def _extract_trace_id(traceparent: str) -> str:
    parts = traceparent.split("-")
    if len(parts) >= 2 and len(parts[1]) == 32:
        return parts[1]
    return uuid4().hex


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(request: Request) -> InvokeResponse:
    body = await request.json()
    trace_id = _extract_trace_id(request.headers.get("traceparent", ""))

    # 兼容单轮扁平输入与多轮 turns 信封
    turns = body.get("input", {}).get("turns")
    if isinstance(turns, list) and turns:
        state = dict(body.get("state") or {})
        merged_tools: list[dict[str, Any]] = []
        last = None
        for turn in turns:
            result = agent.invoke(turn.get("input") or {}, state)
            state = result["final_state"]
            merged_tools.extend(result["tool_events"])
            last = result
        turn_id = turns[-1].get("turn_id")
        output, final_state = last["output"], last["final_state"]
        tool_events = merged_tools
    else:
        result = agent.invoke(body.get("input") or {}, body.get("state") or {})
        output = result["output"]
        final_state = result["final_state"]
        tool_events = result["tool_events"]
        turn_id = body.get("turn_id")

    invocation_id = body.get("invocation_id", "")
    logger.info(
        "invoke run=%s case=%s turn=%s → %s",
        body.get("run_id"), body.get("case_id"), turn_id,
        final_state.get("status"),
    )

    export_trace(
        trace_id=trace_id,
        run_id=body.get("run_id", ""),
        case_id=body.get("case_id", ""),
        turn_id=turn_id,
        invocation_id=invocation_id,
        output=output,
        final_state=final_state,
        tool_events=tool_events,
    )

    return InvokeResponse(
        invocation_id=invocation_id,
        external_execution_id=f"ticket-{uuid4().hex[:12]}",
        output=output,
        final_state=final_state,
        trace_id=trace_id,
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("TICKET_AGENT_PORT", "8090"))
    logger.info("Ticket-Approv-Agent listening on http://127.0.0.1:%s/invoke", port)
    uvicorn.run(app, host="127.0.0.1", port=port)
