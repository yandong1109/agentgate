import pytest

from agentgate.trace.models import OtlpIngestionLimits
from agentgate.trace.normalizer import normalize_otlp_json


def _span(attrs):
    return {"resourceSpans": [{"scopeSpans": [{"spans": [{
        "traceId": "a" * 32, "spanId": "b" * 16, "name": "tool",
        "startTimeUnixNano": "10", "endTimeUnixNano": "20", "attributes": attrs,
    }]}]}]}


def _attr(key, value_key, value):
    return {"key": key, "value": {value_key: value}}


def test_canonical_and_legacy_attributes_are_normalized():
    batch = normalize_otlp_json(_span([
        _attr("agentgate.run_id", "stringValue", "run"),
        _attr("agentgate.case_id", "stringValue", "case"),
        _attr("agentgate.kind", "stringValue", "tool"),
        _attr("nested", "kvlistValue", {"values": [
            _attr("values", "arrayValue", {"values": [
                {"intValue": "1"}, {"boolValue": True},
            ]}),
        ]}),
    ]))
    span = batch.spans[0]
    assert span.run_id == "run" and span.case_id == "case"
    assert span.kind == "tool"
    assert "agentgate.run_id" not in span.attributes
    assert span.attributes["nested"]["values"] == (1, True)
    assert span.start_time_unix_nano == 10


def test_conflicting_aliases_reject_only_the_bad_span():
    batch = normalize_otlp_json(_span([
        _attr("agentgate.run.id", "stringValue", "run-a"),
        _attr("agentgate.run_id", "stringValue", "run-b"),
        _attr("agentgate.case.id", "stringValue", "case"),
    ]))
    assert batch.spans == ()
    assert batch.rejected_spans == 1
    assert "conflicting correlation" in batch.errors[0]


def test_otlp_span_metadata_events_links_and_dropped_counts_are_preserved():
    payload = _span([
        _attr("agentgate.run.id", "stringValue", "run"),
        _attr("agentgate.case.id", "stringValue", "case"),
    ])
    scope = payload["resourceSpans"][0]["scopeSpans"][0]
    scope["scope"] = {"name": "otel.instrumentation", "version": "1.2.3"}
    raw = scope["spans"][0]
    raw.update({
        "kind": 3,
        "status": {"code": 2, "message": "failed"},
        "droppedAttributesCount": 1,
        "droppedEventsCount": 2,
        "droppedLinksCount": 3,
        "events": [{
            "timeUnixNano": "15", "name": "exception",
            "attributes": [_attr("exception.type", "stringValue", "ValueError")],
            "droppedAttributesCount": 4,
        }],
        "links": [{
            "traceId": "c" * 32, "spanId": "d" * 16, "traceState": "vendor=x",
            "attributes": [_attr("link.kind", "stringValue", "follows")],
            "droppedAttributesCount": 5,
        }],
    })
    span = normalize_otlp_json(payload).spans[0]
    assert (span.otel_kind, span.status, span.status_message) == (3, "2", "failed")
    assert (span.scope_name, span.scope_version) == ("otel.instrumentation", "1.2.3")
    assert span.events[0]["name"] == "exception"
    assert span.links[0]["trace_id"] == "c" * 32
    assert (
        span.dropped_attributes_count,
        span.dropped_events_count,
        span.dropped_links_count,
    ) == (1, 2, 3)


def test_limits_distinguish_request_and_span_rejection():
    payload = _span([
        _attr("agentgate.run.id", "stringValue", "run"),
        _attr("agentgate.case.id", "stringValue", "case"),
        _attr("long", "stringValue", "too-long"),
    ])
    partial = normalize_otlp_json(payload, OtlpIngestionLimits(max_string_length=3))
    assert partial.rejected_spans == 1 and partial.spans == ()

    spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    spans.append({**spans[0], "spanId": "c" * 16})
    with pytest.raises(ValueError, match="span limit"):
        normalize_otlp_json(payload, OtlpIngestionLimits(max_spans=1, max_string_length=99))


def test_explicit_null_output_is_a_present_signal_but_absent_is_not():
    payload = _span([
        _attr("agentgate.run.id", "stringValue", "run"),
        _attr("agentgate.case.id", "stringValue", "case"),
        {"key": "agentgate.final.output", "value": {}},
    ])
    batch = normalize_otlp_json(payload)
    assert len(batch.signals) == 1
    assert batch.signals[0].kind == "final_output"
    assert batch.signals[0].value is None

    payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["attributes"].pop()
    assert normalize_otlp_json(payload).signals == ()


def test_legacy_terminal_string_and_json_fields_are_normalized():
    payload = _span([
        _attr("agentgate.run.id", "stringValue", "run"),
        _attr("agentgate.case.id", "stringValue", "case"),
        _attr("agentgate.turn.id", "stringValue", "turn"),
        _attr("agentgate.trace.complete", "stringValue", "true"),
        _attr("agentgate.turn.complete", "stringValue", "true"),
        _attr("agentgate.final_output.json", "stringValue", '{"answer":"ok"}'),
        _attr("agentgate.final_state.json", "stringValue", '{"done":true}'),
    ])

    batch = normalize_otlp_json(payload)

    assert {signal.kind: signal.value for signal in batch.signals} == {
        "trace_complete": True,
        "turn_complete": True,
        "final_output": {"answer": "ok"},
        "final_state": {"done": True},
    }
