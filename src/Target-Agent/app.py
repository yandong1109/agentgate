"""Ticket-Approv-Agent HTTP 服务：实现 AgentGate Invoke 契约。

契约要点（对应 agentgate/src/agentgate/run/targets/http.py）：
- POST /invoke：请求/响应均为 JSON（Content-Type 必须含 json）
- 响应 200 且必含 output 与 final_state；trace_id 建议返回（32 位 hex）
- 头部 traceparent / Idempotency-Key / X-AgentGate-* 照收不拒
- 遥测：默认 trace-sdk 桥接（设 AGENTGATE_TRACE_SDK_FILE_ROOT 时启用，
  事件写入 file 后端目录，AgentGate 接收器拉取）；未设置时回退 OTLP 上报
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from pydantic import BaseModel

from chain import TicketApprovAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("ticket_agent")

# 桥接模块自包含（不依赖 agentgate 包），按仓库布局定位
sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "agentgate" / "contrib")
)
from agentgate_bridge import AgentGateBridge  # noqa: E402

BRIDGE_ROOT = os.getenv("AGENTGATE_TRACE_SDK_FILE_ROOT", "").strip()
if BRIDGE_ROOT:
    bridge = AgentGateBridge(output_root=BRIDGE_ROOT)
else:
    bridge = None

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


def _legacy_otlp_export(body, trace_id, output, final_state, tool_events) -> None:
    """OTLP 回退路径（未配置 trace-sdk 目录时）。"""
    from telemetry import export_trace

    export_trace(
        trace_id=trace_id,
        run_id=body.get("run_id", ""),
        case_id=body.get("case_id", ""),
        turn_id=body.get("turn_id"),
        invocation_id=body.get("invocation_id", ""),
        output=output,
        final_state=final_state,
        tool_events=tool_events,
    )


def _invoke_bridge(
    body: dict[str, Any], headers: dict[str, str],
) -> dict[str, Any]:
    """trace-sdk 桥接路径：逐轮 TurnTrace，响应前已全部落盘（write-through）。"""
    state = dict(body.get("state") or {})
    merged_tools: list[dict[str, Any]] = []
    last = None

    traces = bridge.turn_traces(body, headers)
    turns = (body.get("input") or {}).get("turns")
    if isinstance(turns, list) and turns:
        pairs = [(t, turn.get("input") or {}) for t, turn in zip(traces, turns, strict=True)]
    else:
        pairs = [(traces[0], body.get("input") or {})]

    for turn_trace, turn_input in pairs:
        result = agent.invoke(turn_input, state)
        state = result["final_state"]
        merged_tools.extend(result["tool_events"])
        turn_trace.start()
        for tool_event in result["tool_events"]:
            turn_trace.tool(tool_event["tool"], tool_event.get("args"))
        turn_trace.finish(output=result["output"], final_state=result["final_state"])
        last = result

    assert last is not None
    return {"output": last["output"], "final_state": last["final_state"],
            "tool_events": merged_tools}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(request: Request) -> InvokeResponse:
    body = await request.json()
    headers = {k: v for k, v in request.headers.items()}
    trace_id = _extract_trace_id(request.headers.get("traceparent", ""))

    if bridge is not None:
        result = _invoke_bridge(body, headers)
        output = result["output"]
        final_state = result["final_state"]
    else:
        # 旧路径：直接执行 + OTLP 回退上报
        turns = (body.get("input") or {}).get("turns")
        if isinstance(turns, list) and turns:
            state = dict(body.get("state") or {})
            merged: list[dict[str, Any]] = []
            last = None
            for turn in turns:
                result = agent.invoke(turn.get("input") or {}, state)
                state = result["final_state"]
                merged.extend(result["tool_events"])
                last = result
            output, final_state = last["output"], last["final_state"]
            tool_events = merged
        else:
            result = agent.invoke(body.get("input") or {}, body.get("state") or {})
            output = result["output"]
            final_state = result["final_state"]
            tool_events = result["tool_events"]
        _legacy_otlp_export(body, trace_id, output, final_state, tool_events)

    invocation_id = body.get("invocation_id", "")
    logger.info(
        "invoke run=%s case=%s mode=%s → %s",
        body.get("run_id"), body.get("case_id"),
        "trace-sdk" if bridge is not None else "otlp",
        final_state.get("status"),
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
    logger.info(
        "Ticket-Approv-Agent listening on http://127.0.0.1:%s/invoke (trace=%s)",
        port, "sdk-bridge" if bridge is not None else "otlp-fallback",
    )
    uvicorn.run(app, host="127.0.0.1", port=port)
