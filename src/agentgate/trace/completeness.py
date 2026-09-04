"""Pure Trace completeness policy evaluation."""

from __future__ import annotations

from agentgate.domain import TraceCompletenessPolicy, TraceStatus


def determine_trace_status(
    *,
    policy: TraceCompletenessPolicy,
    turns_complete: bool,
    trace_terminal: bool,
    output_present: bool,
    state_present: bool,
    quiet_elapsed: bool,
    conflict_count: int,
    deadline_elapsed: bool,
) -> TraceStatus:
    """Return status without transport, clock, or persistence dependencies."""
    complete = (
        turns_complete
        and not policy.require_execution_result
        and (not policy.require_terminal_signal or trace_terminal)
        and (not policy.require_final_output or output_present)
        and (not policy.require_final_state or state_present)
        and quiet_elapsed
    )
    if conflict_count:
        return TraceStatus.CONFLICTED
    if complete:
        return TraceStatus.COMPLETE
    if deadline_elapsed:
        return TraceStatus.INCOMPLETE
    return TraceStatus.COLLECTING
