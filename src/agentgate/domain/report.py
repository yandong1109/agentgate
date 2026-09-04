"""Complete API-facing run report."""

from __future__ import annotations

from .base import DomainModel
from .gate import GateDecision
from .metric import MetricSummary
from .result import Result
from .run import Run


class RunReport(DomainModel):
    run: Run
    results: tuple[Result, ...]
    metrics: tuple[MetricSummary, ...]
    gate: GateDecision
