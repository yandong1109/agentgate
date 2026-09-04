"""Runnable LangChain HTTP Agent sample service (§B).

**Current state: OTLP JSON stub.** This service manually constructs OTLP/HTTP
JSON payloads and POSTs them to AgentGate's ``/v1/traces`` receiver. The real
``openinference-instrumentation-langchain`` + OTel SDK exporter wiring is
deferred — the function is equivalent (AgentGate receives OpenInference-style
spans) but not SDK-native output. Dependencies under
``[project.optional-dependencies] demo`` are retained for when real SDK wiring
lands.

A minimal FastAPI service that demonstrates the "real HTTP agent + OTel export"
integration mode. It accepts POST /invoke with the AgentGate TargetExecutionRequest
body, reads the traceparent header for W3C trace context propagation, returns
output/state/trace_id, and exports OpenInference-style OTLP to AgentGate's
/v1/traces receiver.

Run: ``python -m agentgate.demo.langchain_agent``

When no LLM provider key is set, a deterministic stub is used so CI needs no
provider key.
"""

from __future__ import annotations

import json
import os
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from pydantic import BaseModel

app = FastAPI(title="AgentGate LangChain Sample Agent")

OTLP_ENDPOINT = os.getenv("AGENTGATE_OTLP_ENDPOINT", "http://localhost:8000/v1/traces")


class InvokeResponse(BaseModel):
    invocation_id: str
    external_execution_id: str | None = None
    output: dict[str, Any]
    final_state: dict[str, Any]
    trace_id: str


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(request: Request) -> InvokeResponse:
    body = await request.json()
    traceparent = request.headers.get("traceparent", "")
    trace_id = _extract_trace_id(traceparent)

    # Deterministic stub: no LLM provider key required for CI.
    skill = body.get("input", {}).get("skill", "unknown")
    output = {"message": f"processed {skill}", "status": "approved"}
    final_state = {"approved": True, "status": "approved"}

    _export_otlp(trace_id, body.get("run_id", ""), body.get("case_id", ""))

    return InvokeResponse(
        invocation_id=body.get("invocation_id", ""),
        external_execution_id=str(uuid4()),
        output=output,
        final_state=final_state,
        trace_id=trace_id,
    )


def _extract_trace_id(traceparent: str) -> str:
    parts = traceparent.split("-")
    if len(parts) >= 2 and len(parts[1]) == 32:
        return parts[1]
    return uuid4().hex


def _export_otlp(trace_id: str, run_id: str, case_id: str) -> None:
    """Export OpenInference-style OTLP spans to AgentGate's receiver."""
    try:
        import urllib.request

        payload = json.dumps({
            "resourceSpans": [{
                "resource": {"attributes": []},
                "scopeSpans": [{"spans": [
                    {
                        "traceId": trace_id,
                        "spanId": uuid4().hex[:16],
                        "name": "agent.invoke",
                        "attributes": [
                            {"key": "openinference.span.kind", "value": {"stringValue": "AGENT"}},
                            {"key": "llm.model_name", "value": {"stringValue": "demo-model"}},
                        ],
                    },
                    {
                        "traceId": trace_id,
                        "spanId": uuid4().hex[:16],
                        "name": "tool.call",
                        "attributes": [
                            {"key": "openinference.span.kind", "value": {"stringValue": "TOOL"}},
                            {"key": "tool.name", "value": {"stringValue": "approve_loan"}},
                        ],
                    },
                ]}],
            }]
        }).encode("utf-8")
        req = urllib.request.Request(
            OTLP_ENDPOINT, data=payload,
            headers={"content-type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:  # noqa: BLE001, S110 - OTLP export failure is non-fatal
        pass


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("AGENTGATE_LANGCHAIN_AGENT_PORT", "8081"))
    uvicorn.run(app, host="0.0.0.0", port=port)
