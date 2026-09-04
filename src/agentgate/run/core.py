"""RunEngine orchestrates Case-by-Case evaluation against a target adapter."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from agentgate.domain import (
    DatasetVersion,
    DatasetVersionStatus,
    GateSpec,
    MetricPlan,
    Run,
    RunSnapshot,
    RunStatus,
    TargetExecutionRequest,
    TargetSnapshot,
    Trace,
    TraceStatus,
    freeze_json,
)
from agentgate.evaluator import EVALUATORS, evaluate_case, validate_evaluation_plan
from agentgate.result.service import build_report
from agentgate.run.targets.base import TargetExecutionAdapter, TargetIntegrationError
from agentgate.storage.base import AgentGateRepository

LOGGER = logging.getLogger(__name__)


class ExternalSchedulerAdapter(Protocol):
    """Forward-looking boundary for future async/external scheduling."""

    def execute(
        self, adapter: TargetExecutionAdapter, request: TargetExecutionRequest
    ) -> object: ...


class RunEngine:
    def __init__(self, repository: AgentGateRepository) -> None:
        self.repository = repository

    def run(
        self, dataset: DatasetVersion, target_snapshot: TargetSnapshot,
        adapter: TargetExecutionAdapter, evaluators=EVALUATORS,
        *, metric_plan: MetricPlan | None = None, gate_spec: GateSpec | None = None,
        selected_case_ids: tuple[str, ...] | None = None,
        parent_run_id: str | None = None, root_run_id: str | None = None,
        rerun_case_id: str | None = None,
        trace_wait_seconds: float = 30.0, trace_poll_interval_seconds: float = 0.5,
    ) -> Run:
        if dataset.status != DatasetVersionStatus.PUBLISHED:
            raise ValueError("only published Dataset versions can be evaluated")
        selected = tuple(evaluators)
        validate_evaluation_plan(dataset, selected)
        case_ids = {case.id for case in dataset.cases}
        if selected_case_ids is not None:
            if not selected_case_ids:
                raise ValueError("selected Case IDs cannot be empty")
            if len(selected_case_ids) != len(set(selected_case_ids)):
                raise ValueError("selected Case IDs must be unique")
            unknown = set(selected_case_ids) - case_ids
            if unknown:
                raise ValueError(f"unknown selected Cases: {', '.join(sorted(unknown))}")
        snapshot = RunSnapshot(
            dataset=dataset,
            target=target_snapshot,
            evaluator_specs=selected,
            primary_evaluator_ids=tuple(item.id for item in selected),
            metric_plan=metric_plan or MetricPlan(),
            gate_spec=gate_spec or GateSpec(),
            selected_case_ids=selected_case_ids,
        )
        run = Run(
            snapshot=snapshot,
            status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
            parent_run_id=parent_run_id,
            root_run_id=root_run_id,
            rerun_case_id=rerun_case_id,
        )
        self.repository.save_run(run)
        results = []
        trace_warnings: list[str] = []
        try:
            cases = dataset.cases if selected_case_ids is None else tuple(
                case for case in dataset.cases if case.id in set(selected_case_ids)
            )
            for case in cases:
                result = self._invoke_case(run.id, case, target_snapshot, adapter)
                trace = self._resolve_trace(
                    run.id, case, result, trace_wait_seconds,
                    trace_poll_interval_seconds,
                )
                self.repository.save_trace(trace)
                if trace.status != TraceStatus.COMPLETE:
                    raise ValueError(
                        f"trace for case {case.id} is not eligible for evaluation: "
                        f"{trace.status.value}"
                    )
                case_results = evaluate_case(case, trace, snapshot.evaluator_specs)
                results.extend(
                    item.model_copy(update={
                        "trace_revision": trace.revision,
                        "trace_content_sha256": trace.content_sha256,
                    })
                    for item in case_results
                )
            self.repository.save_results(results)
            completed = run.model_copy(update={
                "status": RunStatus.COMPLETED,
                "completed_at": datetime.now(UTC),
                "trace_warnings": tuple(trace_warnings),
            })
            self.repository.save_run(completed)
            return completed
        except Exception as exc:
            failed = run.model_copy(update={
                "status": RunStatus.FAILED,
                "completed_at": datetime.now(UTC),
                "error": str(exc),
                "trace_warnings": tuple(trace_warnings),
            })
            self.repository.save_run(failed)
            raise

    def _invoke_case(self, run_id, case, target_snapshot, adapter):
        invocation_id = str(uuid4())
        idempotency_key = uuid4().hex
        trace_id = uuid4().hex
        parent_span_id = uuid4().hex[:16]
        traceparent = f"00-{trace_id}-{parent_span_id}-01"
        self.repository.put_pending_trace(run_id, case.id, invocation_id, trace_id)
        request = TargetExecutionRequest(
            invocation_id=invocation_id,
            idempotency_key=idempotency_key,
            run_id=run_id,
            case_id=case.id,
            turn_id=None,
            target=target_snapshot,
            input=freeze_json({
                "turns": [
                    {"turn_id": turn.id, "input": turn.input.to_dict()}
                    for turn in case.turns
                ]
            }),
            state=case.initial_state,
            timeout_seconds=float(
                target_snapshot.invocation_config.get("timeout_seconds") or 30.0
            ),
            traceparent=traceparent,
        )
        return adapter.execute(request)

    def _resolve_trace(
        self, run_id, case, result, trace_wait_seconds, poll_interval
    ) -> Trace:
        if result.inline_trace is not None:
            return result.inline_trace
        deadline = time.monotonic() + trace_wait_seconds
        last_status = "missing"
        while time.monotonic() < deadline:
            trace = self.repository.get_trace(run_id, case.id)
            if trace is not None:
                last_status = trace.status.value
                if trace.status in (
                    TraceStatus.COMPLETE,
                    TraceStatus.CONFLICTED,
                    TraceStatus.INCOMPLETE,
                ):
                    return trace
            time.sleep(poll_interval)
        message = (
            f"case {case.id} did not produce a complete trace within "
            f"{trace_wait_seconds}s (trace_id={result.trace_id}, status={last_status})"
        )
        LOGGER.warning("trace_timeout: %s", message)
        raise TargetIntegrationError.trace_timeout(message)

    def report(self, run_id: str):
        run = self.repository.get_run(run_id)
        if run is None:
            return None
        return build_report(run, self.repository.list_results(run_id))
