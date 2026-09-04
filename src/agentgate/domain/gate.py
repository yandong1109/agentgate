"""Release-gate configuration and decisions."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import DomainModel
from .result import Outcome


class GateSpec(DomainModel):
    id: str = "p1-release-gate"
    version: str = "1"
    threshold: float = Field(default=0.95, ge=0, le=1)
    blocking_failure: Literal["veto"] = "veto"
    evaluator_error_behavior: Literal["fail"] = "fail"
    review_behavior: Literal["fail"] = "fail"
    empty_result_behavior: Literal["fail"] = "fail"


class GateDecision(DomainModel):
    outcome: Literal[Outcome.PASS, Outcome.FAIL]
    passed: int
    failed: int
    reviewed: int
    not_applicable: int
    errors: int
    score: float | None = Field(default=None, ge=0, le=1)
    threshold: float = Field(ge=0, le=1)
    reason: str
