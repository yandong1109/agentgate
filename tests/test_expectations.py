import pytest

from agentgate.domain import Equals, MatchesPattern, OneOf, WithinRange


def test_condition_values_are_recursively_immutable():
    source = {"nested": [{"value": 1}]}
    condition = Equals(expected=source)
    source["nested"][0]["value"] = 2
    assert condition.expected["nested"][0]["value"] == 1
    with pytest.raises(TypeError):
        condition.expected["nested"][0]["value"] = 3


def test_condition_construction_rejects_invalid_rules():
    with pytest.raises(ValueError):
        MatchesPattern(pattern="[")
    with pytest.raises(ValueError):
        WithinRange()
    assert OneOf(allowed=({"value": 1},)).allowed[0]["value"] == 1
