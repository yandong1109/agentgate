"""Pre-run validation for a DatasetVersion and selected evaluator definitions."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from agentgate.domain import (
    DatasetVersion,
    HybridEvaluatorSpec,
    Kind,
    MatchesJsonSchema,
    RuleEvaluatorSpec,
)
from agentgate.domain.base import canonical_json

from .models import (
    DuplicateEvaluatorId,
    EvaluatorVersionMismatch,
    InvalidHybridEvaluator,
    MissingEvaluatorDependency,
    SchemaIssue,
)
from .observations import condition_operator
from .registry import resolve_evaluator, resolve_operator

LOGGER = logging.getLogger(__name__)

_SUPPORTED_DRAFT_MARKER = "2020-12"
_REMOTE_REF_PREFIXES = ("http://", "https://", "file://")

_DEFAULT_MAX_DEPTH = 64
_DEFAULT_MAX_SERIALIZED_SIZE = 262144
_MAX_SCHEMA_ERROR_LENGTH = 500


def _resolve_positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        LOGGER.warning("invalid %s=%r, falling back to %d", name, raw, default)
        return default
    if value <= 0:
        LOGGER.warning("invalid %s=%r (must be positive), falling back to %d", name, raw, default)
        return default
    return value


_MAX_DEPTH = _resolve_positive_int_env(
    "AGENTGATE_JSON_SCHEMA_MAX_DEPTH", _DEFAULT_MAX_DEPTH,
)
_MAX_SERIALIZED_SIZE = _resolve_positive_int_env(
    "AGENTGATE_JSON_SCHEMA_MAX_SERIALIZED_SIZE", _DEFAULT_MAX_SERIALIZED_SIZE,
)


def _find_remote_ref(schema: Any) -> str | None:
    if isinstance(schema, dict):
        for key in ("$ref", "$dynamicRef"):
            ref = schema.get(key)
            if isinstance(ref, str) and ref.startswith(_REMOTE_REF_PREFIXES):
                return ref
        for value in schema.values():
            found = _find_remote_ref(value)
            if found is not None:
                return found
    elif isinstance(schema, list):
        for item in schema:
            found = _find_remote_ref(item)
            if found is not None:
                return found
    return None


def _measure_depth(schema: Any) -> int:
    # Explicit stack iteration (not recursion) so an adversarial deep schema
    # cannot trigger RecursionError in the depth check itself. Scalars do not
    # add depth; only dict/list/tuple (Mapping) nesting is counted.
    if not isinstance(schema, (Mapping, list, tuple)):
        return 0
    max_depth = 0
    stack: list[tuple[Any, int]] = [(schema, 1)]
    while stack:
        node, depth = stack.pop()
        max_depth = max(max_depth, depth)
        children = node.values() if isinstance(node, Mapping) else node
        for child in children:
            if isinstance(child, (Mapping, list, tuple)):
                stack.append((child, depth + 1))
    return max_depth


def validate_json_schema(
    schema: Mapping[str, Any], instance_mode: str,
) -> list[SchemaIssue]:
    """Run all JSON Schema input gates (§6.2 order). Empty list = valid.

    ``instance_mode`` is accepted so the precheck API and Run-time path share one
    logic source; the size/depth/draft/ref gates do not depend on it today.
    """
    _ = instance_mode
    if isinstance(schema, Mapping):
        declared = schema.get("$schema")
        if isinstance(declared, str) and _SUPPORTED_DRAFT_MARKER not in declared:
            return [SchemaIssue(
                code="unsupported_draft",
                message=f"unsupported JSON Schema draft: {declared}",
                declared=declared,
            )]
        # canonical_json 的 json.dumps/thaw_json 递归实现；极深 schema（逼近 Python
        # 递归天花板）会在迭代式 _measure_depth 之前抛 RecursionError，兜底返
        # depth_exceeded 以避免预检 500 / Run 前 RecursionError 泄漏。
        try:
            size = len(canonical_json(schema).encode("utf-8"))
        except RecursionError:
            return [SchemaIssue(
                code="depth_exceeded",
                message=f"schema 嵌套深度超过递归天花板，无法精确计数；上限 {_MAX_DEPTH}",
                limit=_MAX_DEPTH,
                actual=None,
            )]
        if size > _MAX_SERIALIZED_SIZE:
            return [SchemaIssue(
                code="size_exceeded",
                message=f"schema 序列化大小 {size} 超过上限 {_MAX_SERIALIZED_SIZE}",
                limit=_MAX_SERIALIZED_SIZE,
                actual=size,
            )]
        depth = _measure_depth(schema)
        if depth > _MAX_DEPTH:
            return [SchemaIssue(
                code="depth_exceeded",
                message=f"schema 嵌套深度 {depth} 超过上限 {_MAX_DEPTH}",
                limit=_MAX_DEPTH,
                actual=depth,
            )]
        remote_ref = _find_remote_ref(schema)
        if remote_ref is not None:
            return [SchemaIssue(
                code="remote_ref_forbidden",
                message=f"remote $ref is not supported: {remote_ref}",
                ref=remote_ref,
            )]
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        message = exc.message
        if len(message) > _MAX_SCHEMA_ERROR_LENGTH:
            message = message[: _MAX_SCHEMA_ERROR_LENGTH - 1].rstrip() + "…"
        return [SchemaIssue(code="invalid_schema", message=f"invalid JSON Schema: {message}")]
    return []


def _validate_json_schema_condition(condition: MatchesJsonSchema) -> None:
    issues = validate_json_schema(condition.json_schema.to_dict(), condition.instance_mode)
    if issues:
        raise ValueError(issues[0].message)


def validate_evaluation_plan(dataset: DatasetVersion, evaluators: tuple) -> None:
    by_id = {item.id: item for item in evaluators}
    if len(by_id) != len(evaluators):
        raise DuplicateEvaluatorId("evaluator IDs must be unique")

    metric_dimensions: dict[str, object] = {}
    for spec in evaluators:
        previous = metric_dimensions.setdefault(spec.metric, spec.dimension)
        if previous != spec.dimension:
            raise ValueError(
                f"metric {spec.metric} cannot belong to both {previous} and {spec.dimension}"
            )
        if isinstance(spec, RuleEvaluatorSpec) and spec.operator:
            resolve_operator(spec.operator, spec.operator_version)
        if isinstance(spec, HybridEvaluatorSpec):
            children = []
            for child in spec.children:
                child_spec = by_id.get(child.evaluator_id)
                if child_spec is None:
                    raise MissingEvaluatorDependency(child.evaluator_id)
                if child.version != child_spec.version:
                    raise EvaluatorVersionMismatch(child.evaluator_id)
                children.append(child_spec)
            if any(item.kind == Kind.HYBRID for item in children):
                raise InvalidHybridEvaluator("nested Hybrid is not supported")
            kinds = {item.kind for item in children}
            if not {Kind.RULE, Kind.LLM_JUDGE}.issubset(kinds):
                raise InvalidHybridEvaluator("Hybrid requires Rule and LLM Judge children")
        resolve_evaluator(spec)

    for case in dataset.cases:
        for turn in case.turns:
            for expectation in turn.expectations:
                if isinstance(expectation.condition, MatchesJsonSchema):
                    _validate_json_schema_condition(expectation.condition)
                resolve_operator(condition_operator(expectation.condition), "1")
