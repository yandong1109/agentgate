"""Python-function target adapter wrapping a callable that returns a Trace."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from agentgate.domain import (
    Case,
    CaseTurn,
    TargetExecutionRequest,
    TargetExecutionResult,
    Trace,
    freeze_json,
)

from .base import TargetIntegrationError


class PythonFunctionTarget:
    """Adapter wrapping a callable ``execute(run_id, case, version) -> Trace``."""

    adapter_type = "python_fn"
    adapter_version = "1"

    def __init__(self, function: Callable[[str, Case, str], Trace]) -> None:
        self.function = function

    def execute(self, request: TargetExecutionRequest) -> TargetExecutionResult:
        version = request.target.ref.external_version_id
        case = _reconstruct_case(request)
        trace = self.function(request.run_id, case, version)
        if trace.run_id != request.run_id or trace.case_id != request.case_id:
            raise TargetIntegrationError.rejected(
                "inline Trace identity does not match request"
            )
        output = trace.final_output.to_dict() if hasattr(trace.final_output, "to_dict") else dict(
            trace.final_output
        )
        return TargetExecutionResult(
            invocation_id=request.invocation_id,
            external_execution_id=None,
            output=freeze_json(output),
            final_state=trace.final_state,
            inline_trace=trace,
            trace_id=trace.spans[0].trace_id if trace.spans else None,
            completed_at=datetime.now(UTC),
        )


def _reconstruct_case(request: TargetExecutionRequest) -> Case:
    """Rebuild a Case for the legacy callable from the serialized request input."""
    turns_data = request.input.get("turns")
    if turns_data:
        turns = tuple(
            CaseTurn(id=item["turn_id"], input=item["input"])
            for item in turns_data
        )
    else:
        turns = (CaseTurn(id=f"{request.case_id}-turn-1", input=request.input),)
    return Case(
        id=request.case_id,
        name=request.case_id,
        initial_state=request.state,
        turns=turns,
    )
