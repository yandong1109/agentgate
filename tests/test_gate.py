from agentgate.domain import (
    CheckResult,
    Dimension,
    FailureObservation,
    FailureStage,
    GateSpec,
    Kind,
    Outcome,
    Result,
    Severity,
)
from agentgate.result.gate import decide_gate


def result(index, outcome=Outcome.PASS, severity=Severity.STANDARD):
    failure = (
        FailureObservation(stage=FailureStage.FINAL_STATE, observed_at_sequence=0)
        if outcome == Outcome.FAIL else None
    )
    return Result(
        run_id="run",
        case_id=str(index),
        evaluator_id=f"e-{index}",
        evaluator_name="e",
        evaluator_version="1",
        evaluator_kind=Kind.RULE,
        dimension=Dimension.SAFETY,
        metric="policy",
        severity=severity,
        outcome=outcome,
        score=1.0 if outcome == Outcome.PASS else 0.0,
        reason="test",
        checks=(CheckResult(
            name="test", outcome=outcome,
            score=1.0 if outcome == Outcome.PASS else 0.0,
            reason="test", failure_observation=failure,
        ),),
        primary_failure_step=FailureStage.FINAL_STATE if failure else None,
    )


def test_one_blocking_failure_cannot_be_averaged_away():
    results = [result(index) for index in range(19)]
    results.append(result(19, Outcome.FAIL, Severity.BLOCKING))
    gate = decide_gate(results, tuple(item.evaluator_id for item in results), GateSpec())
    assert gate.score == 0.95
    assert gate.outcome == Outcome.FAIL


def test_no_applicable_evidence_fails_closed():
    item = result(1).model_copy(update={"outcome": Outcome.NOT_APPLICABLE, "score": None})
    gate = decide_gate([item], (item.evaluator_id,), GateSpec())
    assert gate.outcome == Outcome.FAIL
    assert gate.score is None


def test_evaluator_error_fails_gate_without_agent_score():
    item = result(1).model_copy(update={
        "outcome": Outcome.ERROR,
        "score": None,
        "error_evidence": {
            "category": "crash",
            "exception_type": "RuntimeError",
            "message": "failed",
        },
    })
    gate = decide_gate([item], (item.evaluator_id,), GateSpec())
    assert gate.outcome == Outcome.FAIL
    assert gate.errors == 1
    assert gate.score is None
