"""Collection comparisons used by specialized tool evaluators."""

from __future__ import annotations

from collections.abc import Collection

from ..models import OperatorOutcome
from ..registry import register_operator


@register_operator("contains_all")
def contains_all(actual: Collection[str], expected: Collection[str]) -> OperatorOutcome:
    missing = [item for item in expected if item not in actual]
    reason = "包含所有必需项" if not missing else f"缺少：{', '.join(missing)}"
    return OperatorOutcome(passed=not missing, reason=reason)


@register_operator("contains_none")
def contains_none(actual: Collection[str], forbidden: Collection[str]) -> OperatorOutcome:
    found = [item for item in forbidden if item in actual]
    reason = "未包含禁用项" if not found else f"包含禁用项：{', '.join(found)}"
    return OperatorOutcome(passed=not found, reason=reason)
