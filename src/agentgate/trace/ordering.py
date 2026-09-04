"""Deterministic global ordering for normalized trace spans."""

from __future__ import annotations

from agentgate.trace.models import NormalizedSpan


class SpanOrderingError(ValueError):
    pass


def order_spans(
    spans: list[NormalizedSpan], turn_indexes: dict[str, int] | None = None
) -> list[NormalizedSpan]:
    turn_indexes = turn_indexes or {}
    by_identity = {(span.source_trace_id, span.source_span_id): span for span in spans}
    depths: dict[tuple[str, str], int] = {}

    def depth(identity: tuple[str, str], visiting: set[tuple[str, str]]) -> int:
        if identity in depths:
            return depths[identity]
        if identity in visiting:
            raise SpanOrderingError("parent cycle detected")
        span = by_identity[identity]
        if not span.parent_span_id:
            result = 0
        else:
            parent = (span.source_trace_id, span.parent_span_id)
            result = 0 if parent not in by_identity else depth(parent, visiting | {identity}) + 1
        depths[identity] = result
        return result

    for identity in by_identity:
        depth(identity, set())

    sentinel = 2**63 - 1
    return sorted(spans, key=lambda span: (
        turn_indexes.get(span.turn_id, sentinel),
        span.invocation_attempt,
        span.start_time_unix_nano if span.start_time_unix_nano is not None else sentinel,
        depths[(span.source_trace_id, span.source_span_id)],
        span.end_time_unix_nano if span.end_time_unix_nano is not None else sentinel,
        span.source_trace_id,
        span.source_span_id,
    ))
