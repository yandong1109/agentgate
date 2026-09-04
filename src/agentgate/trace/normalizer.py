"""Normalize bounded OTLP/HTTP JSON or trace-sdk events into trace batches."""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from agentgate.domain import SpanKind, canonical_json, content_sha256, freeze_json
from agentgate.trace.models import (
    NormalizedSignal, NormalizedSpan, OtlpIngestionLimits, TraceBatch, TraceConflict,
)

_TRACE_ID = re.compile(r"^[0-9a-fA-F]{32}$")
_SPAN_ID = re.compile(r"^[0-9a-fA-F]{16}$")
_ALIASES = {
    "agentgate.run.id": ("agentgate.run_id",),
    "agentgate.case.id": ("agentgate.case_id",),
    "agentgate.turn.id": ("turn_id",),
    "agentgate.span.kind": ("agentgate.kind",),
    "agentgate.final.output": ("agentgate.final_output.json",),
    "agentgate.final.state": ("agentgate.final_state.json",),
    "agentgate.trace.complete": (),
    "agentgate.turn.complete": (),
}
_OPENINFERENCE_KIND_MAP = {
    "LLM": SpanKind.AGENT, "AGENT": SpanKind.AGENT, "CHAIN": SpanKind.AGENT,
    "TOOL": SpanKind.TOOL, "RETRIEVER": SpanKind.TOOL,
    "GUARDRAIL": SpanKind.EVENT, "EMBEDDING": SpanKind.EVENT,
    "RERANKER": SpanKind.EVENT,
}


def _resolve_kind(span_attrs: dict[str, Any]) -> SpanKind:
    explicit = span_attrs.get("agentgate.span.kind")
    if isinstance(explicit, str) and explicit in SpanKind._value2member_map_:
        return SpanKind(explicit)
    oi_kind = span_attrs.get("openinference.span.kind")
    if isinstance(oi_kind, str) and oi_kind.upper() in _OPENINFERENCE_KIND_MAP:
        return _OPENINFERENCE_KIND_MAP[oi_kind.upper()]
    if span_attrs.get("gen_ai.system") is not None:
        return SpanKind.AGENT
    if span_attrs.get("gen_ai.tool.name") is not None or span_attrs.get("tool.name") is not None:
        return SpanKind.TOOL
    return SpanKind.EVENT


def otlp_value(
    value: dict[str, Any], limits: OtlpIngestionLimits | None = None, depth: int = 0
) -> Any:
    limits = limits or OtlpIngestionLimits()
    if depth >= limits.max_anyvalue_depth:
        raise ValueError("AnyValue nesting exceeds configured depth")
    if "stringValue" in value:
        result = value["stringValue"]
        if not isinstance(result, str) or len(result) > limits.max_string_length:
            raise ValueError("OTLP string value is invalid or too long")
        return result
    if "boolValue" in value:
        return value["boolValue"]
    if "intValue" in value:
        return int(value["intValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "bytesValue" in value:
        raw = value["bytesValue"]
        decoded = base64.b64decode(raw, validate=True)
        if len(decoded) > limits.max_string_length:
            raise ValueError("OTLP bytes value is too large")
        return raw
    if "arrayValue" in value:
        values = value["arrayValue"].get("values", [])
        if len(values) > limits.max_attributes:
            raise ValueError("OTLP array has too many values")
        return [otlp_value(item, limits, depth + 1) for item in values]
    if "kvlistValue" in value:
        return attributes(value["kvlistValue"].get("values", []), limits, depth + 1)
    return None


def attributes(
    items: list[dict[str, Any]], limits: OtlpIngestionLimits | None = None,
    depth: int = 0,
) -> dict[str, Any]:
    limits = limits or OtlpIngestionLimits()
    if not isinstance(items, list) or len(items) > limits.max_attributes:
        raise ValueError("too many OTLP attributes")
    result: dict[str, Any] = {}
    for item in items:
        key = item.get("key")
        if not isinstance(key, str) or not key or len(key) > limits.max_key_length:
            raise ValueError("attribute key is invalid or too long")
        result[key] = otlp_value(item.get("value", {}), limits, depth)
    return result


def _canonicalize(raw: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(raw)
    for canonical, aliases in _ALIASES.items():
        candidates = [
            (key, _compatibility_value(canonical, key, raw[key]))
            for key in (canonical, *aliases) if key in raw
        ]
        if len({canonical_json(value) for _, value in candidates}) > 1:
            raise ValueError(f"conflicting correlation attributes for {canonical}")
        if candidates:
            normalized[canonical] = candidates[0][1]
        for alias in aliases:
            normalized.pop(alias, None)
    return normalized


def _compatibility_value(canonical: str, source_key: str, value: Any) -> Any:
    """Normalize legacy terminal fields emitted by existing Agent SDKs."""
    if canonical in ("agentgate.trace.complete", "agentgate.turn.complete"):
        if isinstance(value, str) and value.lower() in ("true", "false"):
            return value.lower() == "true"
    if source_key in ("agentgate.final_output.json", "agentgate.final_state.json"):
        if not isinstance(value, str):
            raise ValueError(f"{source_key} must be a JSON string")
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{source_key} contains invalid JSON") from exc
    return value


def _required_string(attrs: dict[str, Any], key: str) -> str:
    value = attrs.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing or invalid {key}")
    return value


def _optional_string(attrs: dict[str, Any], key: str) -> str | None:
    value = attrs.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"invalid {key}")
    return value


def _bounded_string(value: Any, field: str, limits: OtlpIngestionLimits) -> str:
    if not isinstance(value, str) or len(value) > limits.max_string_length:
        raise ValueError(f"{field} is invalid or too long")
    return value


def _timestamp(raw: dict[str, Any], key: str) -> int | None:
    value = raw.get(key)
    if value in (None, ""):
        return None
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"{key} cannot be negative")
    return parsed


def _event(raw: dict[str, Any], limits: OtlpIngestionLimits) -> dict[str, Any]:
    return {
        "time_unix_nano": _timestamp(raw, "timeUnixNano"),
        "name": _bounded_string(raw.get("name", ""), "event name", limits),
        "attributes": attributes(raw.get("attributes", []), limits),
        "dropped_attributes_count": int(raw.get("droppedAttributesCount", 0)),
    }


def _link(raw: dict[str, Any], limits: OtlpIngestionLimits) -> dict[str, Any]:
    trace_id = str(raw.get("traceId", "")).lower()
    span_id = str(raw.get("spanId", "")).lower()
    if not _TRACE_ID.fullmatch(trace_id) or not _SPAN_ID.fullmatch(span_id):
        raise ValueError("link contains an invalid traceId or spanId")
    return {
        "trace_id": trace_id,
        "span_id": span_id,
        "trace_state": _bounded_string(
            raw.get("traceState", ""), "link traceState", limits
        ),
        "attributes": attributes(raw.get("attributes", []), limits),
        "dropped_attributes_count": int(raw.get("droppedAttributesCount", 0)),
    }


def normalize_otlp_json(
    payload: dict[str, Any], limits: OtlpIngestionLimits | None = None, *,
    correlation_resolver: Callable[
        [str], tuple[str, str] | tuple[str, str, str] | None
    ] | None = None,
) -> TraceBatch:
    limits = limits or OtlpIngestionLimits()
    if not isinstance(payload, dict):
        raise ValueError("OTLP payload must be an object")
    resources = payload.get("resourceSpans", [])
    if not isinstance(resources, list) or len(resources) > limits.max_resources:
        raise ValueError("resourceSpans is invalid or exceeds configured limit")
    spans: list[NormalizedSpan] = []
    signals: list[NormalizedSignal] = []
    conflicts: list[TraceConflict] = []
    errors: list[str] = []
    rejected = 0
    span_index = 0
    for resource_span in resources:
        resource_attrs = attributes(
            resource_span.get("resource", {}).get("attributes", []), limits
        )
        scope_spans = resource_span.get(
            "scopeSpans", resource_span.get("instrumentationLibrarySpans", [])
        )
        if not isinstance(scope_spans, list) or len(scope_spans) > limits.max_scopes_per_resource:
            raise ValueError("scopeSpans is invalid or exceeds configured limit")
        for scope_span in scope_spans:
            scope = scope_span.get("scope", scope_span.get("instrumentationLibrary", {}))
            scope_attrs = attributes(scope.get("attributes", []), limits)
            raw_spans = scope_span.get("spans", [])
            if not isinstance(raw_spans, list):
                raise ValueError("spans must be an array")
            if span_index + len(raw_spans) > limits.max_spans:
                raise ValueError("OTLP request exceeds configured span limit")
            for raw in raw_spans:
                span_index += 1
                raw_attrs: dict[str, Any] = {}
                try:
                    raw_attrs = {
                        **resource_attrs,
                        **scope_attrs,
                        **attributes(raw.get("attributes", []), limits),
                    }
                    span_attrs = _canonicalize(raw_attrs)
                    trace_id = str(raw.get("traceId", "")).lower()
                    span_id = str(raw.get("spanId", "")).lower()
                    parent_id = str(raw.get("parentSpanId", "")).lower() or None
                    if not _TRACE_ID.fullmatch(trace_id):
                        raise ValueError("traceId must be 32 hexadecimal characters")
                    if not _SPAN_ID.fullmatch(span_id):
                        raise ValueError("spanId must be 16 hexadecimal characters")
                    if parent_id is not None and not _SPAN_ID.fullmatch(parent_id):
                        raise ValueError("parentSpanId must be 16 hexadecimal characters")
                    resolved = (
                        correlation_resolver(trace_id)
                        if correlation_resolver is not None else None
                    )
                    if (
                        ("agentgate.run.id" not in span_attrs
                         or "agentgate.case.id" not in span_attrs)
                        and resolved is not None
                    ):
                        span_attrs["agentgate.run.id"] = resolved[0]
                        span_attrs["agentgate.case.id"] = resolved[1]
                        if len(resolved) == 3:
                            span_attrs.setdefault("agentgate.invocation.id", resolved[2])
                    run_id = _required_string(span_attrs, "agentgate.run.id")
                    case_id = _required_string(span_attrs, "agentgate.case.id")
                    start = _timestamp(raw, "startTimeUnixNano")
                    end = _timestamp(raw, "endTimeUnixNano")
                    if start is not None and end is not None and end < start:
                        raise ValueError("span end time cannot precede start time")
                    raw_events = raw.get("events", [])
                    raw_links = raw.get("links", [])
                    if len(raw_events) > limits.max_events or len(raw_links) > limits.max_links:
                        raise ValueError("span events or links exceed configured limit")
                    kind = _resolve_kind(span_attrs)
                    attempt_raw = span_attrs.get("agentgate.invocation.attempt", 0)
                    if isinstance(attempt_raw, bool):
                        raise ValueError("invocation attempt must be an integer")
                    attempt = int(attempt_raw)
                    if attempt < 0:
                        raise ValueError("invocation attempt cannot be negative")
                    if "agentgate.final.state" in span_attrs and not isinstance(
                        span_attrs["agentgate.final.state"], dict
                    ):
                        raise ValueError("agentgate.final.state must be a key-value list")
                    status = raw.get("status", {})
                    normalized = NormalizedSpan(
                        run_id=run_id, case_id=case_id,
                        source_trace_id=trace_id, source_span_id=span_id,
                        parent_span_id=parent_id,
                        turn_id=_optional_string(span_attrs, "agentgate.turn.id"),
                        invocation_id=_optional_string(span_attrs, "agentgate.invocation.id"),
                        invocation_attempt=attempt,
                        name=_bounded_string(
                            raw.get("name") or "otlp-span", "span name", limits
                        ),
                        kind=kind,
                        otel_kind=int(raw["kind"]) if "kind" in raw else None,
                        scope_name=(
                            _bounded_string(scope["name"], "scope name", limits)
                            if "name" in scope else None
                        ),
                        scope_version=(
                            _bounded_string(scope["version"], "scope version", limits)
                            if "version" in scope else None
                        ),
                        start_time_unix_nano=start, end_time_unix_nano=end,
                        attributes=span_attrs,
                        events=tuple(_event(item, limits) for item in raw_events),
                        links=tuple(_link(item, limits) for item in raw_links),
                        dropped_attributes_count=int(raw.get("droppedAttributesCount", 0)),
                        dropped_events_count=int(raw.get("droppedEventsCount", 0)),
                        dropped_links_count=int(raw.get("droppedLinksCount", 0)),
                        status=str(status.get("code", "unset")).lower(),
                        status_message=_bounded_string(
                            status.get("message", ""), "status message", limits
                        ),
                    )
                    spans.append(normalized)
                    signal_values = {
                        "trace_complete": "agentgate.trace.complete",
                        "turn_complete": "agentgate.turn.complete",
                        "final_output": "agentgate.final.output",
                        "final_state": "agentgate.final.state",
                    }
                    for signal_kind, attribute_key in signal_values.items():
                        if attribute_key not in span_attrs:
                            continue
                        value = span_attrs[attribute_key]
                        if signal_kind.endswith("complete") and value is not True:
                            continue
                        signals.append(NormalizedSignal(
                            run_id=run_id, case_id=case_id,
                            source_trace_id=trace_id, source_span_id=span_id,
                            turn_id=normalized.turn_id,
                            invocation_id=normalized.invocation_id,
                            kind=signal_kind, value=value,
                        ))
                except (TypeError, ValueError) as exc:
                    rejected += 1
                    message = f"span {span_index}: {exc}"
                    if len(errors) < 20:
                        errors.append(message)
                    if "conflicting correlation" in str(exc):
                        conflicts.append(TraceConflict(
                            kind="correlation",
                            run_id=raw_attrs.get("agentgate.run.id"),
                            case_id=raw_attrs.get("agentgate.case.id"),
                            source_trace_id=str(raw.get("traceId", "")).lower() or None,
                            source_span_id=str(raw.get("spanId", "")).lower() or None,
                            summary=str(exc)[:500],
                        ))
    normalized_size = len(canonical_json({
        "spans": [item.model_dump(mode="json") for item in spans],
        "signals": [item.model_dump(mode="json") for item in signals],
        "conflicts": [item.model_dump(mode="json") for item in conflicts],
    }).encode("utf-8"))
    if normalized_size > limits.max_normalized_bytes:
        raise ValueError("normalized OTLP request exceeds configured byte limit")
    return TraceBatch(
        content_sha256=content_sha256(payload), spans=tuple(spans),
        signals=tuple(signals), conflicts=tuple(conflicts), errors=tuple(errors),
        rejected_spans=rejected,
    )


# ── trace-sdk 事件归一化分支（trace-sdk-integration-plan §Event Normalization）──
#
# 输入为 trace-sdk 的事件 JSON（file 后端 JSONL 逐行 / Redis Stream 消息）。
# 与 OTLP 分支在 NormalizedSpan/NormalizedSignal 处汇合，下游 merge/completeness
# 零改动。冻结契约见 docs/trace/trace-sdk-integration-plan.md 映射表。

TRACE_SDK_BATCH_SOURCE = "trace-sdk"

_EVENT_ID_MAX = 128
_SPAN_TYPE_TO_KIND = {
    "tool": SpanKind.TOOL,
    "retriever": SpanKind.TOOL,
    "agent": SpanKind.AGENT,
    "chain": SpanKind.AGENT,
    "llm": SpanKind.AGENT,
    "span": SpanKind.EVENT,
}
_ROOT_PARENT_VALUES = {"", "root", None}


def _event_id(value: Any, field: str) -> str:
    """trace-sdk 的 span_id/event_id 为 UUID 字符串——放宽为非空有界字符串。"""
    if not isinstance(value, str) or not value.strip() or len(value) > _EVENT_ID_MAX:
        raise ValueError(f"trace-sdk event {field} is missing or invalid")
    return value.strip()


def _iso_to_nano(value: Any, field: str) -> int | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError(f"trace-sdk {field} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"trace-sdk {field} is not valid ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.timestamp() * 1_000_000_000)


def _event_correlation(event: dict[str, Any]) -> dict[str, Any]:
    """桥接约定：关联字段在事件 metadata（agentgate.* 键）。"""
    metadata = event.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _attr_str(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(
        value, ensure_ascii=False, sort_keys=True
    )


def _trace_sdk_span(
    event: dict[str, Any],
    limits: OtlpIngestionLimits,
    correlation_resolver: Callable[
        [str], tuple[str, str] | tuple[str, str, str] | None
    ] | None,
) -> tuple[NormalizedSpan, list[NormalizedSignal]]:
    trace_id = _event_id(event.get("trace_id"), "trace_id")
    span_id = _event_id(event.get("span_id"), "span_id")
    parent = event.get("parent_span_id")
    parent_span_id = None if parent in _ROOT_PARENT_VALUES else _event_id(
        parent, "parent_span_id"
    )

    attrs: dict[str, Any] = {}
    metadata = _event_correlation(event)
    for key in ("run", "case", "turn", "invocation"):
        value = metadata.get(f"agentgate.{key}.id")
        if isinstance(value, str) and value:
            attrs[f"agentgate.{key}.id"] = value
    invocation_id = attrs.get("agentgate.invocation.id")
    if "agentgate.run.id" not in attrs or "agentgate.case.id" not in attrs:
        if correlation_resolver is None:
            raise ValueError("missing agentgate.run.id/case.id and no resolver")
        resolved = correlation_resolver(trace_id)
        if resolved is None:
            raise ValueError(f"unmatched trace_id in pending correlation: {trace_id}")
        attrs.setdefault("agentgate.run.id", resolved[0])
        attrs.setdefault("agentgate.case.id", resolved[1])
        if len(resolved) > 2 and invocation_id is None:
            attrs["agentgate.invocation.id"] = resolved[2]
            invocation_id = resolved[2]

    span_type = event.get("span_type")
    kind = _SPAN_TYPE_TO_KIND.get(
        span_type if isinstance(span_type, str) else "", SpanKind.EVENT
    )
    span_attrs: dict[str, Any] = {
        "trace_sdk.span_type": span_type if isinstance(span_type, str) else "",
    }
    for source_key, attr_key in (
        ("input", "span.input"), ("output", "span.output"),
        ("tool_name", "tool.name"), ("model", "llm.model_name"),
    ):
        if event.get(source_key) is not None:
            span_attrs[attr_key] = _attr_str(event[source_key])
    if isinstance(event.get("error_info"), dict):
        span_attrs["error_info"] = json.dumps(
            event["error_info"], ensure_ascii=False, sort_keys=True
        )
    if metadata:
        span_attrs["trace_sdk.metadata"] = json.dumps(
            metadata, ensure_ascii=False, sort_keys=True
        )

    start = _iso_to_nano(event.get("started_at"), "started_at")
    end = None
    if start is not None and isinstance(event.get("duration_ms"), (int, float)):
        end = start + int(event["duration_ms"] * 1_000_000)
    name = event.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("trace-sdk span name is required")

    span = NormalizedSpan(
        run_id=attrs["agentgate.run.id"],
        case_id=attrs["agentgate.case.id"],
        source_trace_id=trace_id,
        source_span_id=span_id,
        parent_span_id=parent_span_id,
        turn_id=attrs.get("agentgate.turn.id"),
        invocation_id=invocation_id,
        name=name,
        kind=kind,
        start_time_unix_nano=start,
        end_time_unix_nano=end,
        attributes=freeze_json(span_attrs),
        status="error" if event.get("status") == "error" else "unset",
    )
    return span, []


def _trace_sdk_trace_event(
    event: dict[str, Any],
    limits: OtlpIngestionLimits,
    correlation_resolver: Callable[
        [str], tuple[str, str] | tuple[str, str, str] | None
    ] | None,
) -> tuple[NormalizedSpan, list[NormalizedSignal]]:
    """TraceEvent 落地 → terminal EVENT span + trace_complete/turn_complete/final_output。

    信号必须挂在已接受的 span 上（service.ingest 校验信号的 source span），
    故 TraceEvent 同时归一化为一个 ``agent.complete`` EVENT span——与 OTLP 路径
    的 terminal span 模式对称。以 event_id 充当 span 身份（确定性 + 幂等）。
    final_state 不从事件供给（走 invoke 响应，适配器结果优先级最高）。
    """
    trace_id = _event_id(event.get("trace_id"), "trace_id")
    event_id = _event_id(event.get("event_id"), "event_id")
    attrs = _event_correlation(event)
    run_id = attrs.get("agentgate.run.id")
    case_id = attrs.get("agentgate.case.id")
    invocation_id = attrs.get("agentgate.invocation.id")
    turn_id = attrs.get("agentgate.turn.id")
    if not run_id or not case_id:
        if correlation_resolver is None:
            raise ValueError("missing agentgate.run.id/case.id and no resolver")
        resolved = correlation_resolver(trace_id)
        if resolved is None:
            raise ValueError(f"unmatched trace_id in pending correlation: {trace_id}")
        run_id, case_id = resolved[0], resolved[1]
        if invocation_id is None and len(resolved) > 2:
            invocation_id = resolved[2]

    span = NormalizedSpan(
        run_id=run_id, case_id=case_id,
        source_trace_id=trace_id, source_span_id=event_id,
        turn_id=turn_id, invocation_id=invocation_id,
        name="agent.complete", kind=SpanKind.EVENT,
        status="error" if event.get("status") == "error" else "unset",
        attributes=freeze_json({
            "trace_sdk.event_type": "trace",
            "trace_sdk.status": str(event.get("status", "")),
        }),
    )
    signals = [NormalizedSignal(
        run_id=run_id, case_id=case_id,
        source_trace_id=trace_id, source_span_id=event_id,
        turn_id=turn_id,
        invocation_id=invocation_id,
        kind="trace_complete", value=True,
    )]
    # 逐轮完成信号：桥接在 TraceEvent metadata 写 agentgate.turn.id（多轮为每轮
    # 一个 TraceEvent，见 trace-sdk-integration-plan §C-4）。轮次未知时不发——
    # service.ingest 会跳过无轮次的 turn_complete。
    if turn_id:
        signals.append(NormalizedSignal(
            run_id=run_id, case_id=case_id,
            source_trace_id=trace_id, source_span_id=event_id,
            turn_id=turn_id,
            invocation_id=invocation_id,
            kind="turn_complete", value=True,
        ))
    output = event.get("output")
    if output is not None:
        signals.append(NormalizedSignal(
            run_id=run_id, case_id=case_id,
            source_trace_id=trace_id, source_span_id=event_id,
            turn_id=turn_id,
            invocation_id=invocation_id,
            kind="final_output", value=output,
        ))
    # final_state 经桥接写入 metadata（对称 OTLP terminal span 的
    # agentgate.final_state.json 属性；引擎不注入适配器结果，见实现差异记录）
    final_state_raw = attrs.get("agentgate.final_state.json")
    if isinstance(final_state_raw, str) and final_state_raw:
        try:
            final_state_value = json.loads(final_state_raw)
        except json.JSONDecodeError as exc:
            raise ValueError("agentgate.final_state.json is not valid JSON") from exc
        if isinstance(final_state_value, dict):
            signals.append(NormalizedSignal(
                run_id=run_id, case_id=case_id,
                source_trace_id=trace_id, source_span_id=event_id,
                turn_id=turn_id,
                invocation_id=invocation_id,
                kind="final_state", value=final_state_value,
            ))
    return span, signals


def normalize_trace_sdk_events(
    events: list[dict[str, Any]],
    limits: OtlpIngestionLimits | None = None, *,
    correlation_resolver: Callable[
        [str], tuple[str, str] | tuple[str, str, str] | None
    ] | None = None,
) -> TraceBatch:
    """把 trace-sdk 事件列表归一化为 TraceBatch（与 OTLP 分支同一汇合点）。"""
    limits = limits or OtlpIngestionLimits()
    if not isinstance(events, list):
        raise ValueError("trace-sdk events must be a list")
    if len(events) > limits.max_spans:
        raise ValueError("trace-sdk event batch exceeds span limit")

    spans: list[NormalizedSpan] = []
    signals: list[NormalizedSignal] = []
    conflicts: list[TraceConflict] = []
    errors: list[str] = []
    rejected = 0

    for index, event in enumerate(events):
        try:
            if not isinstance(event, dict):
                raise ValueError("event must be an object")
            event_type = event.get("event_type")
            if event_type == "span":
                span, span_signals = _trace_sdk_span(
                    event, limits, correlation_resolver
                )
                spans.append(span)
                signals.extend(span_signals)
            elif event_type == "trace":
                terminal_span, trace_signals = _trace_sdk_trace_event(
                    event, limits, correlation_resolver
                )
                spans.append(terminal_span)
                signals.extend(trace_signals)
            elif event_type == "observation":
                # 冻结契约 v0.1：独立 EVENT span（避免晚到合并造成同 span 伪冲突）
                obs = dict(event)
                obs.setdefault("event_type", "span")
                obs["span_id"] = obs.get("observation_id") or obs.get("event_id")
                obs["name"] = obs.get("name") or "llm.observation"
                obs["span_type"] = "span"
                obs["parent_span_id"] = obs.get("span_id") and event.get("span_id")
                if obs["parent_span_id"] == obs["span_id"]:
                    obs["parent_span_id"] = None
                span, _ = _trace_sdk_span(obs, limits, correlation_resolver)
                span = span.model_copy(update={
                    "kind": SpanKind.EVENT,
                    "name": "llm.observation",
                    "attributes": freeze_json({
                        "llm.observation": json.dumps(
                            {
                                k: event.get(k) for k in
                                ("model", "prompt_tokens", "completion_tokens")
                            }, ensure_ascii=False,
                        ),
                    }),
                })
                spans.append(span)
            elif event_type == "llm_request":
                req = dict(event)
                req["event_type"] = "span"
                req["span_id"] = req.get("event_id")
                req["name"] = "llm.request"
                req["span_type"] = "span"
                req["parent_span_id"] = event.get("span_id")
                span, _ = _trace_sdk_span(req, limits, correlation_resolver)
                span = span.model_copy(update={
                    "kind": SpanKind.EVENT,
                    "name": "llm.request",
                })
                spans.append(span)
            elif event_type == "session":
                continue  # 会话语义与 run/case 不同构，不映射
            else:
                raise ValueError(f"unknown trace-sdk event_type: {event_type!r}")
        except (TypeError, ValueError) as exc:
            rejected += 1
            if len(errors) < 20:
                errors.append(f"event {index}: {exc}")

    batch_payload = json.dumps(events, ensure_ascii=False, sort_keys=True)
    normalized_bytes = len(canonical_json([s.model_dump(mode="json") for s in spans]))
    if normalized_bytes > limits.max_normalized_bytes:
        raise ValueError("normalized trace-sdk batch exceeds byte limit")
    return TraceBatch(
        source=TRACE_SDK_BATCH_SOURCE,
        content_sha256=content_sha256(batch_payload),
        spans=tuple(spans), signals=tuple(signals),
        conflicts=tuple(conflicts), errors=tuple(errors),
        rejected_spans=rejected,
    )
