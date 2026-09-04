import sys
from datetime import UTC, datetime

import pytest

from agentgate.domain import (
    Case,
    CaseTurn,
    DatasetVersion,
    DatasetVersionStatus,
    Dimension,
    MatchesJsonSchema,
    RuleEvaluatorSpec,
    StateExpectation,
)
from agentgate.domain.base import canonical_json
from agentgate.evaluator import EVALUATORS, validate_evaluation_plan
from agentgate.evaluator import validation as evaluator_validation
from agentgate.evaluator.validation import validate_json_schema


def test_valid_demo_plan():
    from agentgate.demo.loan import LOAN_DATASET_VERSION
    validate_evaluation_plan(LOAN_DATASET_VERSION, EVALUATORS)


def _dataset_with(condition):
    return DatasetVersion(
        id="schema-v1",
        dataset_id="schema",
        version=1,
        status=DatasetVersionStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        cases=(Case(
            id="case",
            name="case",
            turns=(CaseTurn(
                id="turn",
                input={"value": "x"},
                expectations=(StateExpectation(
                    path="value",
                    condition=condition,
                ),),
            ),),
        ),),
    )


def test_valid_json_schema_plan_is_accepted():
    dataset = _dataset_with(MatchesJsonSchema(json_schema={"type": "string"}))
    validate_evaluation_plan(dataset, EVALUATORS)


def test_remote_json_schema_ref_is_rejected():
    dataset = _dataset_with(MatchesJsonSchema(
        json_schema={"$ref": "https://example.com/x.json"},
    ))
    with pytest.raises(ValueError, match="remote"):
        validate_evaluation_plan(dataset, EVALUATORS)


def test_remote_dynamic_ref_is_rejected():
    dataset = _dataset_with(MatchesJsonSchema(
        json_schema={"$dynamicRef": "https://example.com/x.json"},
    ))
    with pytest.raises(ValueError, match="remote"):
        validate_evaluation_plan(dataset, EVALUATORS)


def test_local_ref_does_not_mask_remote_dynamic_ref():
    dataset = _dataset_with(MatchesJsonSchema(json_schema={
        "$ref": "#/$defs/pos",
        "$dynamicRef": "https://example.com/x.json",
        "$defs": {"pos": {"type": "integer"}},
    }))
    with pytest.raises(ValueError, match="remote"):
        validate_evaluation_plan(dataset, EVALUATORS)


def test_invalid_json_schema_is_rejected():
    dataset = _dataset_with(MatchesJsonSchema(
        json_schema={"type": "not_a_real_type"},
    ))
    with pytest.raises(ValueError, match="invalid JSON Schema"):
        validate_evaluation_plan(dataset, EVALUATORS)


def test_unsupported_draft_is_rejected():
    dataset = _dataset_with(MatchesJsonSchema(json_schema={
        "$schema": "http://json-schema.org/draft-07/schema#", "type": "string",
    }))
    with pytest.raises(ValueError, match="unsupported JSON Schema draft"):
        validate_evaluation_plan(dataset, EVALUATORS)


def test_one_metric_cannot_map_to_multiple_dimensions():
    dataset = DatasetVersion(dataset_id="empty", cases=())
    specs = (
        RuleEvaluatorSpec(
            id="one", name="one", evaluator_type="final_state",
            dimension=Dimension.STATE, metric="same",
        ),
        RuleEvaluatorSpec(
            id="two", name="two", evaluator_type="final_state",
            dimension=Dimension.TOOL_USE, metric="same",
        ),
    )
    with pytest.raises(ValueError, match="cannot belong"):
        validate_evaluation_plan(dataset, specs)


def _schema_of_size(target_bytes: int) -> dict:
    base = {"type": "string", "description": ""}
    base_size = len(canonical_json(base).encode("utf-8"))
    return {"type": "string", "description": "x" * (target_bytes - base_size)}


def _schema_of_depth(depth: int) -> dict:
    schema = {"type": "string"}
    cur = schema
    for _ in range(depth - 1):
        inner = {"type": "string"}
        cur["nested"] = inner
        cur = inner
    return schema


def test_validate_json_schema_accepts_small_valid_schema():
    assert validate_json_schema({"type": "string"}, "structured") == []


def test_validate_json_schema_rejects_size_exceeded():
    limit = evaluator_validation._MAX_SERIALIZED_SIZE
    schema = _schema_of_size(limit + 1)
    issues = validate_json_schema(schema, "structured")
    assert len(issues) == 1
    assert issues[0].code == "size_exceeded"
    assert issues[0].limit == limit
    assert issues[0].actual == limit + 1
    assert issues[0].actual > issues[0].limit


def test_validate_json_schema_allows_size_at_boundary():
    limit = evaluator_validation._MAX_SERIALIZED_SIZE
    schema = _schema_of_size(limit)
    assert validate_json_schema(schema, "structured") == []


def test_validate_json_schema_rejects_depth_exceeded():
    limit = evaluator_validation._MAX_DEPTH
    schema = _schema_of_depth(limit + 1)
    issues = validate_json_schema(schema, "structured")
    assert len(issues) == 1
    assert issues[0].code == "depth_exceeded"
    assert issues[0].limit == limit
    assert issues[0].actual == limit + 1


def test_validate_json_schema_allows_depth_at_boundary():
    limit = evaluator_validation._MAX_DEPTH
    schema = _schema_of_depth(limit)
    assert validate_json_schema(schema, "structured") == []


def test_validate_json_schema_size_gate_precedes_depth_and_check_schema():
    limit_size = evaluator_validation._MAX_SERIALIZED_SIZE
    limit_depth = evaluator_validation._MAX_DEPTH
    schema = {"type": "not_a_real_type"}
    cur = schema
    for _ in range(limit_depth):
        inner = {"type": "not_a_real_type"}
        cur["nested"] = inner
        cur = inner
    schema["description"] = "x" * (limit_size + 1000)
    issues = validate_json_schema(schema, "structured")
    assert len(issues) == 1
    assert issues[0].code == "size_exceeded"


def test_validate_json_schema_deep_input_does_not_raise_recursion_error():
    schema = _schema_of_depth(500)
    issues = validate_json_schema(schema, "structured")
    assert len(issues) == 1
    assert issues[0].code == "depth_exceeded"


def test_validate_json_schema_extreme_depth_returns_depth_exceeded_not_recursion_error():
    # 对抗性极深 schema（逼近/超过 Python 递归天花板）：迭代构造避免测试自身递归。
    # 默认天花板下由 size 闸门的 RecursionError 兜底返 depth_exceeded（actual=None）；
    # 天花板被调高时由迭代 depth 计数兜住（actual=depth）。两路径均不抛 RecursionError。
    depth = sys.getrecursionlimit() + 100
    schema = _schema_of_depth(depth)
    issues = validate_json_schema(schema, "structured")
    assert len(issues) == 1
    assert issues[0].code == "depth_exceeded"
    assert issues[0].limit == evaluator_validation._MAX_DEPTH
    assert issues[0].actual is None or issues[0].actual > issues[0].limit


def test_validate_json_schema_depth_limit_respects_env_override(monkeypatch):
    monkeypatch.setattr(evaluator_validation, "_MAX_DEPTH", 10)
    issues = validate_json_schema(_schema_of_depth(11), "structured")
    assert len(issues) == 1
    assert issues[0].code == "depth_exceeded"
    assert issues[0].limit == 10
    assert issues[0].actual == 11


def test_resolve_positive_int_env_parses_value(monkeypatch):
    monkeypatch.setenv("AGENTGATE_JSON_SCHEMA_MAX_DEPTH", "10")
    assert evaluator_validation._resolve_positive_int_env(
        "AGENTGATE_JSON_SCHEMA_MAX_DEPTH", 64,
    ) == 10


def test_resolve_positive_int_env_falls_back_on_non_integer(monkeypatch):
    monkeypatch.setenv("AGENTGATE_JSON_SCHEMA_MAX_DEPTH", "abc")
    assert evaluator_validation._resolve_positive_int_env(
        "AGENTGATE_JSON_SCHEMA_MAX_DEPTH", 64,
    ) == 64


def test_resolve_positive_int_env_falls_back_on_non_positive(monkeypatch):
    monkeypatch.setenv("AGENTGATE_JSON_SCHEMA_MAX_DEPTH", "-5")
    assert evaluator_validation._resolve_positive_int_env(
        "AGENTGATE_JSON_SCHEMA_MAX_DEPTH", 64,
    ) == 64


def test_resolve_positive_int_env_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("AGENTGATE_JSON_SCHEMA_MAX_DEPTH", raising=False)
    assert evaluator_validation._resolve_positive_int_env(
        "AGENTGATE_JSON_SCHEMA_MAX_DEPTH", 64,
    ) == 64
