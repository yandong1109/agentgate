import pytest

from agentgate.domain import (
    Case,
    CaseTurn,
    TargetExecutionRequest,
    TargetRef,
    TargetSnapshot,
    TargetType,
    Trace,
)
from agentgate.run.targets.base import TargetIntegrationError
from agentgate.run.targets.python_fn import PythonFunctionTarget


def _snapshot(version: str = "v1") -> TargetSnapshot:
    return TargetSnapshot(
        ref=TargetRef(
            platform_id="demo", target_type=TargetType.AGENT,
            external_target_id="t", external_version_id=version,
        ),
        display_name="test",
        adapter_type="python_fn",
        adapter_version="1",
    )


def _request(case, snapshot, run_id="run"):
    return TargetExecutionRequest(
        invocation_id="inv",
        idempotency_key="key",
        run_id=run_id,
        case_id=case.id,
        target=snapshot,
        input={"turns": [
            {"turn_id": t.id, "input": t.input.to_dict()} for t in case.turns
        ]},
        traceparent="00-" + "0" * 32 + "-" + "0" * 16 + "-01",
    )


def test_python_function_target_wraps_callable_and_returns_inline_trace():
    case = Case(
        id="case", name="case",
        turns=(CaseTurn(id="turn", input={"message": "hello"}),),
    )

    def function(run_id, received_case, version):
        return Trace(
            run_id=run_id,
            case_id=received_case.id,
            spans=(),
            final_output={"version": version, "message": received_case.turns[0].input["message"]},
        )

    adapter = PythonFunctionTarget(function)
    result = adapter.execute(_request(case, _snapshot("v1")))
    assert result.inline_trace is not None
    assert result.output == {"version": "v1", "message": "hello"}
    assert result.trace_id is None


def test_python_function_target_rejects_identity_mismatch():
    case = Case(id="case", name="case", turns=(CaseTurn(id="turn", input={}),))

    def function(run_id, received_case, version):
        return Trace(run_id="wrong", case_id=received_case.id, spans=())

    adapter = PythonFunctionTarget(function)

    with pytest.raises(TargetIntegrationError, match="identity"):
        adapter.execute(_request(case, _snapshot()))
