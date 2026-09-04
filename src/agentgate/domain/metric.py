"""Metric aggregation plan and calculated summaries."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import DomainModel


class MetricPlan(DomainModel):
    id: str = "p1-equal-mean"
    version: str = "1"
    primary_only: Literal[True] = True
    exclude_not_applicable: Literal[True] = True
    result_within_case_aggregation: Literal["equal_mean"] = "equal_mean"
    case_to_metric_aggregation: Literal["equal_mean"] = "equal_mean"
    metric_to_dimension_aggregation: Literal["equal_mean"] = "equal_mean"
    filtered_metric_to_kind_aggregation: Literal["equal_mean"] = "equal_mean"
    dimension_to_overall_aggregation: Literal["equal_mean"] = "equal_mean"
    overall_source: Literal["dimensions_only"] = "dimensions_only"


class MetricSummary(DomainModel):
    key: str
    label: str
    level: Literal["overall", "kind", "dimension", "metric"]
    score: float | None = Field(default=None, ge=0, le=1)
    passed: int = 0
    failed: int = 0
    reviewed: int = 0
    not_applicable: int = 0
    errors: int = 0
    applicable: int = 0
    total: int = 0
    incomplete: bool = False
