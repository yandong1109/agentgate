import pytest

from agentgate.trace.models import NormalizedSpan
from agentgate.trace.ordering import SpanOrderingError, order_spans


def _span(span_id, *, parent=None, start=None):
    return NormalizedSpan(
        run_id="run", case_id="case", source_trace_id="a" * 32,
        source_span_id=span_id, parent_span_id=parent, name=span_id,
        start_time_unix_nano=start,
    )


def test_order_is_arrival_independent_and_parent_precedes_child():
    root = _span("1" * 16, start=100)
    child = _span("2" * 16, parent=root.source_span_id, start=100)
    assert order_spans([child, root]) == [root, child]
    assert order_spans([root, child]) == [root, child]


def test_parent_cycle_is_rejected_deterministically():
    first = _span("1" * 16, parent="2" * 16)
    second = _span("2" * 16, parent="1" * 16)
    with pytest.raises(SpanOrderingError, match="cycle"):
        order_spans([first, second])
