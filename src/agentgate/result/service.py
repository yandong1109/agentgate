"""Construct complete reports without hidden metric or Gate defaults."""

from agentgate.domain import Result, Run, RunReport

from .calc_metrics import calculate_metrics
from .gate import decide_gate


def build_report(run: Run, results: list[Result]) -> RunReport:
    snapshot = run.snapshot
    metrics = calculate_metrics(
        results, snapshot.primary_evaluator_ids, snapshot.metric_plan
    )
    gate = decide_gate(results, snapshot.primary_evaluator_ids, snapshot.gate_spec)
    return RunReport(run=run, results=tuple(results), metrics=metrics, gate=gate)
