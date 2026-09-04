from agentgate.domain import WithinRange, WithinTolerance
from agentgate.evaluator.operators.collection import contains_all, contains_none
from agentgate.evaluator.operators.comparison import within_range, within_tolerance


def test_numeric_operators_reject_bool_and_apply_boundaries():
    assert within_range(5, WithinRange(minimum=1, maximum=5)).passed
    assert not within_range(True, WithinRange(minimum=1)).passed
    assert within_tolerance(0.3, WithinTolerance(expected=0.1 + 0.2)).passed


def test_readable_collection_operators():
    assert contains_all({"a", "b"}, ("a",)).passed
    assert not contains_all({"a"}, ("a", "b")).passed
    assert contains_none({"a"}, ("b",)).passed
    assert not contains_none({"a"}, ("a",)).passed
