import pytest
from pydantic import TypeAdapter, ValidationError

from agentgate.domain import (
    Case,
    CaseTurn,
    EvaluatorSpec,
    MatchesJsonSchema,
    RuleEvaluatorSpec,
    StateExpectation,
    WithinRange,
    content_sha256,
)


def test_expectation_and_evaluator_discriminated_unions():
    case = Case(
        id="case",
        name="case",
        turns=(CaseTurn(
            id="turn",
            input={"message": "hello"},
            expectations=({"kind": "state", "path": "status",
                           "condition": {"kind": "equals", "expected": "ok"}},),
        ),),
    )
    assert isinstance(case.turns[0].expectations[0], StateExpectation)
    spec = TypeAdapter(EvaluatorSpec).validate_python({
        "kind": "rule", "id": "state", "name": "state", "version": "1",
        "dimension": "state", "metric": "state_match",
        "evaluator_type": "final_state",
    })
    assert isinstance(spec, RuleEvaluatorSpec)


def test_range_and_operator_pair_validation():
    with pytest.raises(ValidationError):
        WithinRange()
    with pytest.raises(ValidationError):
        WithinRange(minimum=2, maximum=1)
    with pytest.raises(ValidationError):
        RuleEvaluatorSpec(
            id="x", name="x", dimension="state", metric="x",
            evaluator_type="final_state", operator="equals",
        )


def test_matches_json_schema_instance_mode_serialization():
    condition = MatchesJsonSchema(
        json_schema={"type": "string"},
        instance_mode="json_text",
    )
    dumped = condition.model_dump(mode="json")
    assert dumped["instance_mode"] == "json_text"
    assert dumped["kind"] == "matches_json_schema"
    assert dumped["json_schema"] == {"type": "string"}

    default_condition = MatchesJsonSchema(json_schema={"type": "string"})
    assert default_condition.instance_mode == "structured"
    assert default_condition.model_dump(mode="json")["instance_mode"] == "structured"


def test_instance_mode_affects_content_hash():
    structured = MatchesJsonSchema(json_schema={"type": "object"}, instance_mode="structured")
    json_text = MatchesJsonSchema(json_schema={"type": "object"}, instance_mode="json_text")
    assert content_sha256(structured) != content_sha256(json_text)
