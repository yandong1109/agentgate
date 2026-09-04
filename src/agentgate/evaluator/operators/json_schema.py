"""JSON Schema Draft 2020-12 validation operator."""

from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from agentgate.domain import MatchesJsonSchema
from agentgate.domain.base import thaw_json

from ..models import OperatorOutcome
from ..observations import MISSING
from ..registry import register_operator

_MAX_VIOLATIONS = 20
_MAX_REASON_LENGTH = 500


def _sort_key(path) -> tuple:
    # Path elements are int (array index) or str (object key); mixing them in a
    # plain tuple comparison raises TypeError on Python 3. Tag each element so
    # ints sort among themselves numerically and strs lexicographically without
    # cross-type comparison.
    return tuple((0, p) if isinstance(p, int) else (1, str(p)) for p in path)


def _format_violations(errors: list[ValidationError]) -> str:
    ordered = sorted(
        errors,
        key=lambda e: (
            _sort_key(e.absolute_path),
            _sort_key(e.absolute_schema_path),
            e.message,
        ),
    )
    lines = [f"{e.json_path}: {e.message}" for e in ordered[:_MAX_VIOLATIONS]]
    summary = "; ".join(lines)
    if len(summary) > _MAX_REASON_LENGTH:
        summary = summary[: _MAX_REASON_LENGTH - 1].rstrip() + "…"
    return summary


@register_operator("matches_json_schema")
def matches_json_schema(actual: Any, condition: MatchesJsonSchema) -> OperatorOutcome:
    if actual is MISSING:
        return OperatorOutcome(passed=False, reason="观测值缺失，无法校验 JSON Schema")

    schema = condition.json_schema.to_dict()

    if condition.instance_mode == "json_text":
        if not isinstance(actual, str):
            return OperatorOutcome(passed=False, reason="json_text 模式要求字符串输入")
        try:
            instance = json.loads(actual)
        except json.JSONDecodeError as exc:
            return OperatorOutcome(passed=False, reason=f"JSON 文本解析失败：{exc.msg}")
    else:
        instance = actual

    instance = thaw_json(instance)

    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(instance))
    if not errors:
        return OperatorOutcome(passed=True, reason="输出符合 JSON Schema")
    return OperatorOutcome(passed=False, reason=_format_violations(errors))
