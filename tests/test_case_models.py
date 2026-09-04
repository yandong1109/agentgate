from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from agentgate.domain import (
    Case,
    CaseCategory,
    CaseDifficulty,
    CaseTurn,
    DatasetVersion,
    DatasetVersionStatus,
)


def test_case_has_typed_single_and_multi_turn_forms():
    case = Case(
        name="multi",
        category=CaseCategory.BOUNDARY,
        difficulty=CaseDifficulty.HARD,
        turns=(
            CaseTurn(id="one", input={"message": "申请贷款"}),
            CaseTurn(id="two", input={"amount": 80000}),
        ),
    )
    assert len(case.turns) == 2
    assert case.turns[1].input["amount"] == 80000


def test_published_version_requires_number_and_timestamp():
    with pytest.raises(ValidationError):
        DatasetVersion(
            dataset_id="dataset",
            status=DatasetVersionStatus.PUBLISHED,
            cases=(),
        )
    version = DatasetVersion(
        dataset_id="dataset",
        version=1,
        status=DatasetVersionStatus.PUBLISHED,
        published_at=datetime.now(UTC),
    )
    assert version.content_sha256
