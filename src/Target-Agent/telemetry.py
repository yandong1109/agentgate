"""OTLP 遥测导出：Ticket-Approv-Agent → AgentGate /v1/traces。

评测闭环的关键（AgentGate 评估器消费的是规范化 Trace，不是 invoke 响应）：
- 业务 span 带 openinference.span.kind（AGENT/TOOL）与 tool.name
- terminal span 携带完整性信号：agentgate.trace.complete / turn.complete /
  final_output.json / final_state.json（trace/completeness.py 依此判定 COMPLETE）
- 关联：traceId 取自请求头 traceparent（与引擎的 pending 关联匹配），
  同时带 agentgate.run.id / agentgate.case.id 双保险
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from uuid import uuid4

logger = logging.getLogger("ticket_agent.telemetry")

OTLP_ENDPOINT = os.getenv("AGENTGATE_OTLP_ENDPOINT", "http://127.0.0.1:8010/v1/traces")


def _attr(key: str, value: Any) -> dict:
    return {"key": key, "value": {"stringValue": str(value)}}


def export_trace(
    *,
    trace_id: str,
    run_id: str,
    case_id: str,
    turn_id: str | None,
    invocation_id: str,
    output: dict[str, Any],
    final_state: dict[str, Any],
    tool_events: list[dict[str, Any]],
) -> None:
    """同步导出（先于响应返回），保证引擎轮询 trace 时已可判定完整。"""
    spans: list[dict] = [
        {
            "traceId": trace_id,
            "spanId": uuid4().hex[:16],
            "name": "agent.invoke",
            "attributes": [
                _attr("openinference.span.kind", "AGENT"),
                _attr("llm.model_name", "ticket-approv-stub"),
                _attr("agentgate.run.id", run_id),
                _attr("agentgate.case.id", case_id),
            ],
        },
        *[
            {
                "traceId": trace_id,
                "spanId": uuid4().hex[:16],
                # 契约要点：OTLP span 的 name 必须就是工具名本身
                # （评估器按 span.name == required_tools 匹配，见
                #   evaluator/rules/tool_use.py + trace/merge.py；
                #   tool.name 属性仅用于 TOOL kind 识别）
                "name": event["tool"],
                "attributes": [
                    _attr("openinference.span.kind", "TOOL"),
                    _attr("tool.name", event["tool"]),
                    _attr("tool.arguments", json.dumps(event["args"], ensure_ascii=False)),
                ],
            }
            for event in tool_events
        ],
        # terminal span：完整性信号，trace/completeness.py 依此收敛为 COMPLETE
        {
            "traceId": trace_id,
            "spanId": uuid4().hex[:16],
            "name": "agent.complete",
            "attributes": [
                _attr("agentgate.span.kind", "event"),
                _attr("agentgate.run.id", run_id),
                _attr("agentgate.case.id", case_id),
                _attr("agentgate.turn.id", turn_id or ""),
                _attr("agentgate.invocation.id", invocation_id),
                _attr("agentgate.trace.complete", "true"),
                _attr("agentgate.turn.complete", "true"),
                _attr("agentgate.final_output.json", json.dumps(output, ensure_ascii=False)),
                _attr("agentgate.final_state.json", json.dumps(final_state, ensure_ascii=False)),
            ],
        },
    ]
    payload = json.dumps({
        "resourceSpans": [{
            "resource": {"attributes": []},
            "scopeSpans": [{"spans": spans}],
        }],
    }).encode("utf-8")
    try:
        import urllib.request

        request = urllib.request.Request(
            OTLP_ENDPOINT, data=payload,
            headers={"content-type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(request, timeout=5)
    except Exception as exc:  # noqa: BLE001 - 遥测失败不阻断业务响应
        logger.warning("OTLP 导出失败（不阻断响应）: %s", exc)
