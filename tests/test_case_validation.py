import pytest

from agentgate.case import DatasetValidationError, validate_dataset_version
from agentgate.domain import (
    Case,
    CaseTurn,
    DatasetVersion,
    Equals,
    MatchesJsonSchema,
    StateExpectation,
)


def test_validation_rejects_empty_dataset_and_overlapping_tools():
    with pytest.raises(DatasetValidationError) as empty:
        validate_dataset_version(DatasetVersion(dataset_id="dataset"))
    assert empty.value.issues[0].path == "cases"

    version = DatasetVersion(
        dataset_id="dataset",
        cases=(Case(
            name="bad",
            turns=(CaseTurn(
                input={"skill": "loan_approval"},
                required_tools=("approve_loan",),
                forbidden_tools=("approve_loan",),
            ),),
        ),),
    )
    with pytest.raises(DatasetValidationError, match="同时"):
        validate_dataset_version(version)


def test_validation_accepts_multi_turn_expectations():
    version = DatasetVersion(
        dataset_id="dataset",
        cases=(Case(
            name="multi",
            turns=(
                CaseTurn(input={"message": "hello"}),
                CaseTurn(
                    input={"skill": "credit_inquiry", "application_id": "A-1"},
                    expectations=(StateExpectation(
                        path="risk", condition=Equals(expected="low")
                    ),),
                ),
            ),
        ),),
    )
    validate_dataset_version(version)


def test_validation_rejects_blank_case_and_turn_ids():
    version = DatasetVersion(
        dataset_id="dataset",
        cases=(Case(
            id=" ",
            name="bad IDs",
            turns=(CaseTurn(id="", input={"message": "hello"}),),
        ),),
    )
    with pytest.raises(DatasetValidationError) as error:
        validate_dataset_version(version)
    paths = {item.path for item in error.value.issues}
    assert "cases[0].id" in paths
    assert "cases[0].turns[0].id" in paths


def test_validation_accepts_json_schema_condition():
    version = DatasetVersion(
        dataset_id="dataset",
        cases=(Case(
            name="schema",
            turns=(CaseTurn(
                id="turn",
                input={"skill": "loan_approval"},
                expectations=(StateExpectation(
                    path="risk",
                    condition=MatchesJsonSchema(json_schema={
                        "type": "object",
                        "required": ["level"],
                        "properties": {"level": {"type": "string"}},
                    }),
                ),),
            ),),
        ),),
    )
    validate_dataset_version(version)
