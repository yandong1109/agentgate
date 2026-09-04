"""Pure canonical Trace reconstruction from normalized evidence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from agentgate.domain import (
    Case, Trace, TraceCompletenessPolicy, TraceSpan, TraceStatus, TraceTurn,
    canonical_span_id, canonical_trace_id,
)
from agentgate.trace.models import NormalizedSignal, NormalizedSpan
from agentgate.trace.ordering import SpanOrderingError, order_spans
from agentgate.trace.completeness import determine_trace_status


def _select_signal(
    signals: list[NormalizedSignal], kind: str, turn_id: str | None
) -> tuple[bool, Any]:
    candidates = [item for item in signals if item.kind == kind and item.turn_id == turn_id]
    if not candidates:
        return False, None
    candidates.sort(key=lambda item: (
        -item.precedence, item.content_sha256, item.source_trace_id, item.source_span_id
    ))
    return True, candidates[0].value


def build_canonical_trace(
    run_id: str,
    case_id: str,
    spans: list[NormalizedSpan],
    *,
    signals: list[NormalizedSignal] | None = None,
    case: Case | None = None,
    policy: TraceCompletenessPolicy | None = None,
    conflict_count: int = 0,
    revision: int = 1,
    last_evidence_at: datetime | None = None,
    now: datetime | None = None,
    deadline_elapsed: bool = False,
) -> Trace:
    signals = signals or []
    policy = policy or TraceCompletenessPolicy()
    now = now or datetime.now(UTC)
    turn_indexes = {
        turn.id: index for index, turn in enumerate(case.turns)
    } if case else {}
    try:
        ordered = order_spans(spans, turn_indexes)
    except SpanOrderingError:
        ordered = sorted(spans, key=lambda item: (
            item.source_trace_id, item.source_span_id
        ))

    epoch = datetime.fromtimestamp(0, UTC)
    canonical_spans = tuple(
        TraceSpan(
            id=canonical_span_id(run_id, case_id, span.source_trace_id, span.source_span_id),
            trace_id=span.source_trace_id,
            parent_id=span.parent_span_id,
            source_trace_id=span.source_trace_id,
            source_span_id=span.source_span_id,
            run_id=run_id,
            case_id=case_id,
            turn_id=span.turn_id,
            invocation_id=span.invocation_id,
            invocation_attempt=span.invocation_attempt,
            otel_kind=span.otel_kind,
            scope_name=span.scope_name,
            scope_version=span.scope_version,
            name=span.name,
            kind=span.kind,
            sequence=sequence,
            started_at=(
                datetime.fromtimestamp(span.start_time_unix_nano / 1_000_000_000, UTC)
                if span.start_time_unix_nano is not None else epoch
            ),
            ended_at=(
                datetime.fromtimestamp(span.end_time_unix_nano / 1_000_000_000, UTC)
                if span.end_time_unix_nano is not None else epoch
            ),
            start_time_unix_nano=span.start_time_unix_nano,
            end_time_unix_nano=span.end_time_unix_nano,
            attributes=span.attributes,
            events=span.events,
            links=span.links,
            dropped_attributes_count=span.dropped_attributes_count,
            dropped_events_count=span.dropped_events_count,
            dropped_links_count=span.dropped_links_count,
            status=span.status,
            status_message=span.status_message,
        )
        for sequence, span in enumerate(ordered)
    )

    turns: list[TraceTurn] = []
    for index, case_turn in enumerate(case.turns if case else ()):
        output_present, output = _select_signal(signals, "final_output", case_turn.id)
        state_present, state = _select_signal(signals, "final_state", case_turn.id)
        completed = any(
            item.kind == "turn_complete" and item.turn_id == case_turn.id
            and item.value is True for item in signals
        )
        invocation_ids = tuple(sorted({
            span.invocation_id for span in ordered
            if span.turn_id == case_turn.id and span.invocation_id is not None
        }))
        turns.append(TraceTurn(
            turn_id=case_turn.id, turn_index=index, input=case_turn.input,
            output_present=output_present, output=output,
            state_present=state_present, state=state if state_present else {},
            invocation_ids=invocation_ids, completed=completed,
        ))

    completed_turns = [turn for turn in turns if turn.completed]
    last_turn = completed_turns[-1] if completed_turns else None
    output_present = last_turn.output_present if last_turn else False
    output = last_turn.output if last_turn else None
    state_present = last_turn.state_present if last_turn else False
    state = last_turn.state if last_turn else {}
    if not turns:
        output_present, output = _select_signal(signals, "final_output", None)
        state_present, state = _select_signal(signals, "final_state", None)

    trace_terminal = any(
        item.kind == "trace_complete" and item.value is True for item in signals
    )
    expected_turns = policy.expected_turn_count
    turns_complete = True
    if case:
        expected_turns = expected_turns or len(case.turns)
        turns_complete = len(completed_turns) >= expected_turns
    quiet_elapsed = (
        policy.quiet_period_ms == 0
        or last_evidence_at is None
        or now >= last_evidence_at + timedelta(milliseconds=policy.quiet_period_ms)
    )
    status = determine_trace_status(
        policy=policy, turns_complete=turns_complete,
        trace_terminal=trace_terminal, output_present=output_present,
        state_present=state_present, quiet_elapsed=quiet_elapsed,
        conflict_count=conflict_count, deadline_elapsed=deadline_elapsed,
    )

    end_times = [span.end_time_unix_nano for span in spans
                 if span.end_time_unix_nano is not None]
    completed_at = None
    if status == TraceStatus.COMPLETE and end_times:
        completed_at = datetime.fromtimestamp(max(end_times) / 1_000_000_000, UTC)
    return Trace(
        id=canonical_trace_id(run_id, case_id), run_id=run_id, case_id=case_id,
        status=status, revision=revision, spans=canonical_spans, turns=tuple(turns),
        final_output_present=output_present, final_output=output,
        final_state_present=state_present, final_state=state if state_present else {},
        conflict_count=conflict_count, completed_at=completed_at,
    )
