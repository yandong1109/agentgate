"""Acceptance tests for the matches_json_schema operator (Draft 2020-12)."""

from types import SimpleNamespace

from jsonschema import Draft202012Validator

from agentgate.domain import (
    Case,
    CaseTurn,
    Dimension,
    MatchesJsonSchema,
    Outcome,
    OutputExpectation,
    RuleEvaluatorSpec,
    Trace,
    TraceTurn,
)
from agentgate.domain.base import FrozenJsonObject
from agentgate.evaluator import evaluate_case
from agentgate.evaluator.observations import MISSING
from agentgate.evaluator.operators.json_schema import _format_violations, matches_json_schema


def _schema(schema, *, instance_mode="structured"):
    return MatchesJsonSchema(json_schema=schema, instance_mode=instance_mode)


def test_valid_nested_object_passes():
    schema = {
        "type": "object",
        "required": ["user"],
        "properties": {
            "user": {
                "type": "object",
                "required": ["id", "name"],
                "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
            },
        },
    }
    outcome = matches_json_schema({"user": {"id": 1, "name": "alice"}}, _schema(schema))
    assert outcome.passed
    assert outcome.reason == "输出符合 JSON Schema"


def test_missing_required_field_fails():
    schema = {
        "type": "object",
        "required": ["a", "b"],
        "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
    }
    outcome = matches_json_schema({"a": "x"}, _schema(schema))
    assert not outcome.passed
    assert "b" in outcome.reason
    assert "required" in outcome.reason.lower()


def test_incorrect_field_type_fails():
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    outcome = matches_json_schema({"a": 1}, _schema(schema))
    assert not outcome.passed
    assert "$.a" in outcome.reason


def test_enum_and_const_mismatch_fail():
    enum_outcome = matches_json_schema("blue", _schema({"enum": ["red", "green"]}))
    assert not enum_outcome.passed
    const_outcome = matches_json_schema(7, _schema({"const": 42}))
    assert not const_outcome.passed


def test_numeric_range_violation_fails():
    schema = {"type": "integer", "minimum": 1, "maximum": 10}
    outcome = matches_json_schema(20, _schema(schema))
    assert not outcome.passed


def test_unexpected_property_fails_with_additional_properties_false():
    schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "additionalProperties": False,
    }
    outcome = matches_json_schema({"a": "x", "b": "y"}, _schema(schema))
    assert not outcome.passed
    assert "b" in outcome.reason


def test_array_item_failure_reports_instance_path():
    schema = {"type": "array", "items": {"type": "integer"}}
    outcome = matches_json_schema([1, "two", 3], _schema(schema))
    assert not outcome.passed
    assert "$[1]" in outcome.reason


def test_local_defs_reference_works():
    schema = {
        "$defs": {"pos": {"type": "integer", "minimum": 0}},
        "$ref": "#/$defs/pos",
    }
    assert matches_json_schema(5, _schema(schema)).passed
    assert not matches_json_schema(-1, _schema(schema)).passed


def test_structured_mode_does_not_parse_json_looking_string():
    string_schema = {"type": "string"}
    assert matches_json_schema('{"a": 1}', _schema(string_schema)).passed

    object_schema = {"type": "object"}
    outcome = matches_json_schema('{"a": 1}', _schema(object_schema))
    assert not outcome.passed


def test_json_text_mode_parses_valid_text():
    schema = {"type": "object", "properties": {"a": {"type": "integer"}}}
    outcome = matches_json_schema('{"a": 1}', _schema(schema, instance_mode="json_text"))
    assert outcome.passed


def test_malformed_json_text_is_measured_fail():
    schema = {"type": "object"}
    outcome = matches_json_schema("not json", _schema(schema, instance_mode="json_text"))
    assert not outcome.passed
    assert "解析" in outcome.reason


def test_json_text_mode_requires_string_input():
    schema = {"type": "object"}
    outcome = matches_json_schema({"a": 1}, _schema(schema, instance_mode="json_text"))
    assert not outcome.passed
    assert "json_text" in outcome.reason


def test_missing_differs_from_explicit_json_null():
    schema = {"type": "object"}
    missing = matches_json_schema(MISSING, _schema(schema))
    assert not missing.passed
    assert "缺失" in missing.reason

    explicit_null = matches_json_schema(None, _schema(schema))
    assert not explicit_null.passed
    assert "缺失" not in explicit_null.reason


def test_violations_are_sorted_and_bounded():
    schema = {"type": "array", "items": {"type": "string"}}
    actual = list(range(30))
    outcome = matches_json_schema(actual, _schema(schema))
    assert not outcome.passed
    assert len(outcome.reason) <= 500
    assert outcome.reason.startswith("$[0]")
    assert "$[0]" in outcome.reason
    assert "$[1]" in outcome.reason
    assert "$[29]" not in outcome.reason


def test_violation_count_capped_at_twenty_with_short_messages():
    schema = {"type": "array", "items": {"const": "x"}}
    actual = [chr(ord("a") + i) for i in range(30)]
    outcome = matches_json_schema(actual, _schema(schema))
    assert not outcome.passed
    assert "$[19]" in outcome.reason
    assert "$[20]" not in outcome.reason


def test_reason_length_capped_for_many_long_messages():
    schema = {"type": "object", "additionalProperties": False}
    actual = {f"very_long_property_name_{i}": i for i in range(40)}
    outcome = matches_json_schema(actual, _schema(schema))
    assert not outcome.passed
    assert len(outcome.reason) <= 500


def test_violation_sort_handles_mixed_int_str_paths():
    errors = [
        SimpleNamespace(
            absolute_path=[0], absolute_schema_path=["items", "type"],
            json_path="$[0]", message="array item error",
        ),
        SimpleNamespace(
            absolute_path=["name"], absolute_schema_path=["properties", "name", "type"],
            json_path="$.name", message="object key error",
        ),
    ]
    reason = _format_violations(errors)
    assert "$[0]" in reason
    assert "$.name" in reason


def test_frozen_json_object_is_normalized_for_library_validation():
    schema = {
        "type": "object",
        "required": ["decision"],
        "properties": {"decision": {"type": "string"}},
    }
    frozen = FrozenJsonObject({"decision": "approve"})
    assert matches_json_schema(frozen, _schema(schema)).passed

    nested = FrozenJsonObject({"items": (FrozenJsonObject({"id": 1}),)})
    nested_schema = {
        "type": "object",
        "required": ["items"],
        "properties": {"items": {"type": "array", "items": {"type": "object"}}},
    }
    assert matches_json_schema(nested, _schema(nested_schema)).passed


_FINAL_OUTPUT_SPEC = RuleEvaluatorSpec(
    id="final-output", name="最终输出", evaluator_type="final_output",
    dimension=Dimension.ANSWER, metric="final_output_match",
)


def _output_case_and_trace(condition, output_obj):
    case = Case(
        id="case", name="case",
        turns=(CaseTurn(
            id="turn", input={"message": "hello"},
            expectations=(OutputExpectation(path=None, condition=condition),),
        ),),
    )
    trace = Trace(
        run_id="run", case_id="case", spans=(),
        turns=(TraceTurn(turn_id="turn", input={"message": "hello"}, output=output_obj),),
    )
    return case, trace


def test_library_crash_becomes_error_not_fail(monkeypatch):
    def _crash(self, instance):
        raise RuntimeError("jsonschema library internal crash")

    monkeypatch.setattr(Draft202012Validator, "iter_errors", _crash)

    condition = MatchesJsonSchema(json_schema={"type": "object"})
    case, trace = _output_case_and_trace(condition, {"decision": "approve"})
    results = evaluate_case(case, trace, (_FINAL_OUTPUT_SPEC,))

    assert results[0].outcome == Outcome.ERROR
    assert results[0].outcome != Outcome.FAIL
    assert results[0].score is None
    assert results[0].error_evidence is not None
    assert results[0].error_evidence.category == "crash"
    assert results[0].error_evidence.exception_type == "RuntimeError"
