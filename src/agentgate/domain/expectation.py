"""Expected target-agent outcomes and their conditions."""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import Field, field_validator, model_validator

from .base import DomainModel, FrozenJsonObject, freeze_json


class Equals(DomainModel):
    kind: Literal["equals"] = "equals"
    expected: Any

    @field_validator("expected", mode="before")
    @classmethod
    def freeze_expected(cls, value: Any) -> Any:
        return freeze_json(value)


class WithinTolerance(DomainModel):
    kind: Literal["within_tolerance"] = "within_tolerance"
    expected: float
    epsilon: float = Field(default=1e-6, gt=0)


class WithinRange(DomainModel):
    kind: Literal["within_range"] = "within_range"
    minimum: float | None = None
    maximum: float | None = None

    @model_validator(mode="after")
    def validate_bounds(self) -> WithinRange:
        if self.minimum is None and self.maximum is None:
            raise ValueError("within_range requires minimum or maximum")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum must not exceed maximum")
        return self


class MatchesPattern(DomainModel):
    kind: Literal["matches_pattern"] = "matches_pattern"
    pattern: str

    @model_validator(mode="after")
    def validate_pattern(self) -> MatchesPattern:
        try:
            re.compile(self.pattern)
        except re.error as exc:
            raise ValueError(f"invalid regular expression: {exc}") from exc
        return self


class OneOf(DomainModel):
    kind: Literal["one_of"] = "one_of"
    allowed: tuple[Any, ...]

    @field_validator("allowed", mode="before")
    @classmethod
    def freeze_allowed(cls, value: Any) -> tuple[Any, ...]:
        return tuple(freeze_json(item) for item in value)


class MustBeMissing(DomainModel):
    kind: Literal["must_be_missing"] = "must_be_missing"


class MatchesJsonSchema(DomainModel):
    kind: Literal["matches_json_schema"] = "matches_json_schema"
    json_schema: FrozenJsonObject
    instance_mode: Literal["structured", "json_text"] = "structured"


Condition = Annotated[
    Equals | WithinTolerance | WithinRange | MatchesPattern | OneOf | MustBeMissing |
    MatchesJsonSchema,
    Field(discriminator="kind"),
]


class StateExpectation(DomainModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    kind: Literal["state"] = "state"
    path: str
    condition: Condition
    name: str | None = None


class ToolArgumentExpectation(DomainModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    kind: Literal["tool_argument"] = "tool_argument"
    tool: str
    path: str
    occurrence: Literal["first", "last", "any", "all"] = "last"
    condition: Condition
    name: str | None = None


class OutputExpectation(DomainModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    kind: Literal["output"] = "output"
    path: str | None = None
    condition: Condition
    name: str | None = None


Expectation = Annotated[
    StateExpectation | ToolArgumentExpectation | OutputExpectation,
    Field(discriminator="kind"),
]
