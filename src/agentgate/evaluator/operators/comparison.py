"""Pure single-value Condition comparisons."""

from __future__ import annotations

import re
from typing import Any

from agentgate.domain import (
    Equals,
    MatchesPattern,
    MustBeMissing,
    OneOf,
    WithinRange,
    WithinTolerance,
)

from ..models import OperatorOutcome
from ..observations import MISSING
from ..registry import register_operator


def _numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@register_operator("equals")
def equals(actual: Any, condition: Equals) -> OperatorOutcome:
    passed = actual is not MISSING and actual == condition.expected
    reason = "值相等" if passed else f"实际值 {actual!r} 不等于 {condition.expected!r}"
    return OperatorOutcome(passed=passed, reason=reason)


@register_operator("within_tolerance")
def within_tolerance(actual: Any, condition: WithinTolerance) -> OperatorOutcome:
    passed = _numeric(actual) and abs(float(actual) - condition.expected) <= condition.epsilon
    return OperatorOutcome(passed=passed, reason="数值在容差内" if passed else "数值超出允许容差")


@register_operator("within_range")
def within_range(actual: Any, condition: WithinRange) -> OperatorOutcome:
    passed = _numeric(actual)
    if passed and condition.minimum is not None:
        passed = actual >= condition.minimum
    if passed and condition.maximum is not None:
        passed = actual <= condition.maximum
    return OperatorOutcome(passed=passed, reason="数值在范围内" if passed else "数值不在允许范围内")


@register_operator("matches_pattern")
def matches_pattern(actual: Any, condition: MatchesPattern) -> OperatorOutcome:
    passed = isinstance(actual, str) and re.search(condition.pattern, actual) is not None
    return OperatorOutcome(passed=passed, reason="文本符合格式" if passed else "文本不符合格式")


@register_operator("is_one_of")
def is_one_of(actual: Any, condition: OneOf) -> OperatorOutcome:
    passed = actual is not MISSING and actual in condition.allowed
    return OperatorOutcome(passed=passed, reason="值在允许集合中" if passed else "值不在允许集合中")


@register_operator("must_be_missing")
def must_be_missing(actual: Any, _condition: MustBeMissing) -> OperatorOutcome:
    passed = actual is MISSING
    return OperatorOutcome(passed=passed, reason="字段不存在" if passed else "字段存在但预期不存在")
