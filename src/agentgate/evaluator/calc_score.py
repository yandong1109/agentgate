"""Convert detailed evaluator checks into one persisted Result."""

from __future__ import annotations

from agentgate.domain import (
    CheckResult,
    EvaluatorSpec,
    Evidence,
    FailureObservation,
    MethodRef,
    Outcome,
    Result,
    Trace,
)

from .models import CheckDraft, Evaluation


def _finalize_check(draft: CheckDraft, trace: Trace) -> CheckResult:
    observation = None
    if draft.outcome == Outcome.FAIL:
        if draft.failure is None:
            raise ValueError("failed check has no failure candidate")
        if draft.failure.span_id:
            span = next((item for item in trace.spans if item.id == draft.failure.span_id), None)
            if span is None:
                raise ValueError(f"failure references unknown span: {draft.failure.span_id}")
            sequence = span.sequence
        else:
            sequence = trace.completion_sequence()
        observation = FailureObservation(
            stage=draft.failure.stage,
            observed_at_sequence=sequence,
            span_id=draft.failure.span_id,
        )
    evidence = (
        Evidence(trace_id=trace.id, span_ids=draft.span_ids, description=draft.reason),
    )
    return CheckResult(
        name=draft.name,
        turn_id=draft.turn_id,
        expectation_id=draft.expectation_id,
        outcome=draft.outcome,
        score=draft.score,
        reason=draft.reason,
        expected=draft.expected,
        actual=draft.actual,
        actual_missing=draft.actual_missing,
        methods=draft.methods,
        evidence=evidence,
        failure_observation=observation,
    )


def calculate_result(
    spec: EvaluatorSpec, run_id: str, case_id: str, trace: Trace, evaluation: Evaluation
) -> Result:
    checks = tuple(_finalize_check(item, trace) for item in evaluation.checks)
    applicable = [item for item in checks if item.outcome != Outcome.NOT_APPLICABLE]
    if not applicable:
        outcome, score, reason = Outcome.NOT_APPLICABLE, None, "该用例没有适用检查"
    else:
        failed = [item for item in applicable if item.outcome == Outcome.FAIL]
        reviewed = [item for item in applicable if item.outcome == Outcome.REVIEW]
        score = sum(item.score or 0.0 for item in applicable) / len(applicable)
        if failed:
            outcome, reason = Outcome.FAIL, "；".join(item.reason for item in failed)
        elif reviewed:
            outcome, reason = Outcome.REVIEW, "需要人工复核"
        else:
            outcome, reason = Outcome.PASS, "所有适用检查均通过"

    methods: list[MethodRef] = []
    for check in checks:
        for method in check.methods:
            if method not in methods:
                methods.append(method)
    failed_checks = [item for item in checks if item.failure_observation is not None]
    primary = (
        min(
            enumerate(failed_checks),
            key=lambda pair: (pair[1].failure_observation.observed_at_sequence, pair[0]),
        )[1].failure_observation.stage
        if failed_checks else None
    )
    return Result(
        run_id=run_id,
        case_id=case_id,
        evaluator_id=spec.id,
        evaluator_name=spec.name,
        evaluator_version=spec.version,
        evaluator_kind=spec.kind,
        dimension=spec.dimension,
        metric=spec.metric,
        severity=spec.severity,
        outcome=outcome,
        score=score,
        reason=reason,
        checks=checks,
        methods=tuple(methods),
        evidence=tuple(item for check in checks for item in check.evidence),
        judge_evidence=evaluation.judge_evidence,
        primary_failure_step=primary,
    )
