"""L1 契约测试：trace-sdk 事件归一化分支（冻结映射表逐条验证）。

映射契约见 docs/trace/trace-sdk-integration-plan.md §事件归一化映射表。
"""

import pytest

from agentgate.trace.normalizer import (
    TRACE_SDK_BATCH_SOURCE,
    normalize_trace_sdk_events,
)

TRACE_ID = "ab" * 16
META = {
    "agentgate.run.id": "run-1",
    "agentgate.case.id": "case-1",
    "agentgate.invocation.id": "inv-1",
}


def _span(**overrides):
    event = {
        "event_type": "span",
        "trace_id": TRACE_ID,
        "span_id": "span-0001",
        "name": "review_ticket",
        "span_type": "tool",
        "metadata": dict(META),
        "started_at": "2026-09-04T03:00:00Z",
        "duration_ms": 120,
    }
    event.update(overrides)
    return event


def _trace_event(**overrides):
    event = {
        "event_type": "trace",
        "event_id": "event-0001",
        "trace_id": TRACE_ID,
        "metadata": dict(META),
        "status": "success",
        "output": {"status": "ok"},
    }
    event.update(overrides)
    return event


@pytest.mark.parametrize(("span_type", "expected_kind"), [
    ("tool", "tool"),
    ("retriever", "tool"),
    ("agent", "agent"),
    ("chain", "agent"),
    ("llm", "agent"),
    ("span", "event"),
    ("whatever-unknown", "event"),
    (None, "event"),
])
def test_span_type_maps_to_span_kind(span_type, expected_kind):
    batch = normalize_trace_sdk_events([_span(span_type=span_type)])
    assert len(batch.spans) == 1
    assert batch.spans[0].kind.value == expected_kind


def test_span_correlation_from_metadata():
    batch = normalize_trace_sdk_events([_span(
        metadata={**META, "agentgate.turn.id": "turn-1"},
    )])
    span = batch.spans[0]
    assert span.run_id == "run-1"
    assert span.case_id == "case-1"
    assert span.turn_id == "turn-1"
    assert span.invocation_id == "inv-1"


def test_span_correlation_resolver_fallback():
    """metadata 缺关联时按 pending 关联（trace_id 匹配）补齐——与 OTLP 路径同款。"""
    def resolver(trace_id):
        assert trace_id == TRACE_ID
        return ("run-9", "case-9", "inv-9")

    batch = normalize_trace_sdk_events(
        [_span(metadata={})], correlation_resolver=resolver,
    )
    span = batch.spans[0]
    assert (span.run_id, span.case_id, span.invocation_id) == ("run-9", "case-9", "inv-9")


def test_span_unmatched_trace_id_rejected():
    batch = normalize_trace_sdk_events(
        [_span(metadata={})],
        correlation_resolver=lambda trace_id: None,
    )
    assert batch.spans == ()
    assert batch.rejected_spans == 1
    assert "unmatched trace_id" in batch.errors[0]


def test_trace_event_emits_terminal_span_and_signals():
    """契约：TraceEvent → agent.complete EVENT span + 完成信号（信号须挂在 span 上）。"""
    batch = normalize_trace_sdk_events([_trace_event(
        metadata={**META, "agentgate.turn.id": "turn-1"},
    )])
    assert len(batch.spans) == 1
    span = batch.spans[0]
    assert span.name == "agent.complete"
    assert span.kind.value == "event"
    assert span.source_span_id == "event-0001"
    kinds = [(s.kind, s.source_span_id) for s in batch.signals]
    assert kinds == [
        ("trace_complete", "event-0001"),
        ("turn_complete", "event-0001"),
        ("final_output", "event-0001"),
    ]
    assert batch.signals[0].value is True
    assert batch.signals[2].value == {"status": "ok"}


def test_trace_event_without_turn_id_skips_turn_complete():
    """轮次未知不发 turn_complete（service.ingest 也会跳过无轮次的该信号）。"""
    batch = normalize_trace_sdk_events([_trace_event()])
    assert [s.kind for s in batch.signals] == ["trace_complete", "final_output"]


def test_trace_event_final_state_via_metadata():
    """契约：final_state 经 metadata agentgate.final_state.json 携带（对称 OTLP）。"""
    batch = normalize_trace_sdk_events([_trace_event(
        metadata={**META, "agentgate.turn.id": "t1",
                  "agentgate.final_state.json": '{"approved": false}'},
    )])
    assert [s.kind for s in batch.signals] == [
        "trace_complete", "turn_complete", "final_output", "final_state",
    ]
    assert batch.signals[3].value == {"approved": False}


def test_trace_event_invalid_final_state_rejected():
    batch = normalize_trace_sdk_events([_trace_event(
        metadata={**META, "agentgate.final_state.json": "{not-json"},
    )])
    assert batch.rejected_spans == 1


def test_trace_event_without_output_omits_final_output():
    batch = normalize_trace_sdk_events([_trace_event(output=None)])
    assert [s.kind for s in batch.signals] == ["trace_complete"]


def test_trace_event_error_status_still_completes():
    """契约：TraceEvent 落地即 trace 级完成（success/error 均视为完成）。"""
    batch = normalize_trace_sdk_events([_trace_event(status="error")])
    assert batch.signals[0].kind == "trace_complete"
    assert batch.signals[0].value is True


@pytest.mark.parametrize("root_value", ["", "root", None])
def test_parent_span_id_root_normalized(root_value):
    batch = normalize_trace_sdk_events([_span(parent_span_id=root_value)])
    assert batch.spans[0].parent_span_id is None


def test_parent_span_id_passthrough():
    batch = normalize_trace_sdk_events([_span(parent_span_id="span-0000")])
    assert batch.spans[0].parent_span_id == "span-0000"


def test_uuid_span_ids_accepted():
    """trace-sdk span_id 是 UUID 字符串（非 OTLP 16-hex），归一化分支放宽校验。"""
    batch = normalize_trace_sdk_events([
        _span(span_id="7be8f0e2-1c3d-4e5f-9a6b-2c3d4e5f6a7b"),
    ])
    assert len(batch.spans) == 1
    assert len(batch.spans[0].source_span_id) == 36


def test_status_error_maps_to_span_status():
    batch = normalize_trace_sdk_events([_span(status="error")])
    assert batch.spans[0].status == "error"


def test_timestamps_iso_to_nano():
    batch = normalize_trace_sdk_events([_span(duration_ms=1000)])
    span = batch.spans[0]
    assert span.start_time_unix_nano is not None
    assert span.end_time_unix_nano == span.start_time_unix_nano + 1_000_000_000


def test_span_input_output_and_tool_name_attributes():
    batch = normalize_trace_sdk_events([_span(
        input={"ticket": "T-1"}, output={"approved": True},
        tool_name="review_ticket", model="gpt-4o",
    )])
    attrs = batch.spans[0].attributes.to_dict()
    assert attrs["span.input"] == '{"ticket": "T-1"}'
    assert attrs["tool.name"] == "review_ticket"
    assert attrs["llm.model_name"] == "gpt-4o"


def test_session_event_not_mapped():
    batch = normalize_trace_sdk_events([
        {"event_type": "session", "session_id": "s1", "trace_id": TRACE_ID},
    ])
    assert batch.spans == () and batch.signals == ()
    assert batch.rejected_spans == 0


def test_observation_becomes_independent_event_span():
    """冻结契约 v0.1：observation 为独立 EVENT span（避免晚到合并造成伪冲突）。"""
    batch = normalize_trace_sdk_events([{
        "event_type": "observation",
        "observation_id": "obs-1",
        "event_id": "obs-e1",
        "trace_id": TRACE_ID,
        "span_id": "span-0001",
        "model": "gpt-4o",
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "metadata": dict(META),
    }])
    assert len(batch.spans) == 1
    span = batch.spans[0]
    assert span.name == "llm.observation"
    assert span.kind.value == "event"
    assert span.source_span_id == "obs-1"
    assert span.parent_span_id == "span-0001"


def test_llm_request_becomes_independent_event_span():
    batch = normalize_trace_sdk_events([{
        "event_type": "llm_request",
        "event_id": "req-e1",
        "trace_id": TRACE_ID,
        "span_id": "span-0001",
        "model": "gpt-4o",
        "metadata": dict(META),
    }])
    assert batch.spans[0].name == "llm.request"
    assert batch.spans[0].kind.value == "event"


def test_unknown_event_type_rejected():
    batch = normalize_trace_sdk_events([{"event_type": "weird"}])
    assert batch.rejected_spans == 1
    assert "unknown trace-sdk event_type" in batch.errors[0]


@pytest.mark.parametrize("event", [
    {"event_type": "span", "span_id": "s"},                       # 缺 trace_id
    {"event_type": "span", "trace_id": TRACE_ID},                 # 缺 span_id
    {"event_type": "span", "trace_id": TRACE_ID, "span_id": "s", "metadata": {}},  # 缺关联
    "not-a-dict",
])
def test_invalid_events_rejected_individually(event):
    batch = normalize_trace_sdk_events([_span(), event])
    assert len(batch.spans) == 1
    assert batch.rejected_spans == 1


def test_batch_source_and_idempotency():
    events = [_span(), _trace_event()]
    first = normalize_trace_sdk_events(events)
    second = normalize_trace_sdk_events(events)

    assert first.source == TRACE_SDK_BATCH_SOURCE == "trace-sdk"
    # 同一批事件重放：批次哈希、span 身份四元组/内容、信号 id 全部确定性（幂等的基础）
    assert first.content_sha256 == second.content_sha256
    s1, s2 = first.spans[0], second.spans[0]
    assert (s1.run_id, s1.case_id, s1.source_trace_id, s1.source_span_id) == (
        s2.run_id, s2.case_id, s2.source_trace_id, s2.source_span_id
    )
    assert first.signals[0].id == second.signals[0].id
    assert first.signals[0].content_sha256 == second.signals[0].content_sha256
