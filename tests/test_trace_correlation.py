"""Trace correlation tests: pending mapping, OpenInference kind, degraded fallback.

Covers acceptance #11-15.
"""

from datetime import UTC, datetime

import pytest

from agentgate.domain import (
    DatasetVersion,
    DatasetVersionStatus,
    TargetExecutionRequest,
    TargetExecutionResult,
    TargetRef,
    TargetSnapshot,
    TargetType,
    freeze_json,
)
from agentgate.evaluator import EVALUATORS
from agentgate.run.core import RunEngine
from agentgate.run.targets.base import TargetIntegrationError
from agentgate.storage.sqlite import SQLiteRepository
from agentgate.trace.normalizer import normalize_otlp_json

# -- Pending mapping correlation (#11) --


def test_trace_correlated_by_trace_id_via_pending_mapping(tmp_path):
    repo = SQLiteRepository(tmp_path / "trace.db")
    trace_id = "a" * 32
    repo.put_pending_trace("run-1", "case-1", "inv-1", trace_id)
    payload = _otlp_payload(trace_id=trace_id, kind="AGENT", name="agent.invoke")
    resolver = lambda tid: (
        (pending.run_id, pending.case_id)
        if (pending := repo.get_pending_trace(tid)) else None
    )
    batch = normalize_otlp_json(payload, correlation_resolver=resolver)
    assert len(batch.spans) == 1
    assert batch.spans[0].run_id == "run-1"
    assert batch.spans[0].case_id == "case-1"


def test_uncorrelated_trace_is_rejected(tmp_path):
    repo = SQLiteRepository(tmp_path / "trace.db")
    payload = _otlp_payload(trace_id="f" * 32, kind="AGENT", name="span")
    resolver = lambda tid: repo.get_pending_trace(tid) and (
        repo.get_pending_trace(tid).run_id, repo.get_pending_trace(tid).case_id
    ) or None
    batch = normalize_otlp_json(payload, correlation_resolver=resolver)
    assert batch.spans == ()
    assert len(batch.errors) == 1


# -- agentgate.* priority (#12) --


def test_agentgate_attrs_take_priority_over_pending_mapping(tmp_path):
    repo = SQLiteRepository(tmp_path / "trace.db")
    trace_id = "c" * 32
    repo.put_pending_trace("pending-run", "pending-case", "inv", trace_id)
    payload = {
        "resourceSpans": [{"resource": {"attributes": [
            {"key": "agentgate.run_id", "value": {"stringValue": "explicit-run"}},
            {"key": "agentgate.case_id", "value": {"stringValue": "explicit-case"}},
        ]}, "scopeSpans": [{"spans": [{
            "traceId": trace_id, "spanId": "d" * 16, "name": "span",
            "attributes": [{"key": "agentgate.kind", "value": {"stringValue": "agent"}}],
        }]}]}]}
    batch = normalize_otlp_json(payload, correlation_resolver=lambda t: ("pending", "pending"))
    assert batch.spans[0].run_id == "explicit-run"
    assert batch.spans[0].case_id == "explicit-case"


# -- OpenInference / gen_ai kind mapping (#13) --


@pytest.mark.parametrize(("oi_kind", "expected"), [
    ("LLM", "agent"), ("AGENT", "agent"), ("CHAIN", "agent"),
    ("TOOL", "tool"), ("RETRIEVER", "tool"),
    ("GUARDRAIL", "event"), ("EMBEDDING", "event"), ("RERANKER", "event"),
])
def test_openinference_span_kind_mapping(oi_kind, expected):
    payload = _otlp_payload(trace_id="1" * 32, kind="EVENT", name="s", oi_kind=oi_kind)
    batch = normalize_otlp_json(payload, correlation_resolver=lambda _: ("run", "case"))
    assert batch.spans[0].kind == expected


def test_gen_ai_system_maps_to_agent():
    payload = _otlp_payload(trace_id="2" * 32, kind="EVENT", name="s", extra_attrs=[
        {"key": "gen_ai.system", "value": {"stringValue": "openai"}},
    ])
    batch = normalize_otlp_json(payload, correlation_resolver=lambda _: ("run", "case"))
    assert batch.spans[0].kind == "agent"


def test_gen_ai_tool_name_maps_to_tool():
    payload = _otlp_payload(trace_id="3" * 32, kind="EVENT", name="s", extra_attrs=[
        {"key": "gen_ai.tool.name", "value": {"stringValue": "search"}},
    ])
    batch = normalize_otlp_json(payload, correlation_resolver=lambda _: ("run", "case"))
    assert batch.spans[0].kind == "tool"


# -- Degraded fallback (#14) --


def test_trace_timeout_fails_run_without_evaluation(tmp_path):
    repo = SQLiteRepository(tmp_path / "degraded.db")
    engine = RunEngine(repo)
    snapshot = _http_snapshot()
    dataset = _minimal_dataset()
    with pytest.raises(TargetIntegrationError, match="trace_timeout"):
        engine.run(
            dataset, snapshot, _NoTraceAdapter(), EVALUATORS,
            trace_wait_seconds=0.1, trace_poll_interval_seconds=0.05,
        )
    run = repo.list_runs()[0]
    assert run.status == "failed"
    assert repo.list_results(run.id) == []


# -- Invocation errors stop evaluation, never Agent FAIL (#15) --


def test_invocation_error_marks_run_failed_not_agent_fail(tmp_path):
    repo = SQLiteRepository(tmp_path / "error.db")
    engine = RunEngine(repo)
    snapshot = _http_snapshot()
    dataset = _minimal_dataset()
    with pytest.raises(TargetIntegrationError, match="unavailable"):
        engine.run(dataset, snapshot, _ErrorAdapter(), EVALUATORS)
    runs = repo.list_runs()
    assert runs[0].status == "failed"
    assert "unavailable" in (runs[0].error or "")


# -- Helpers --


def _otlp_payload(trace_id, kind="EVENT", name="span", oi_kind=None, extra_attrs=None):
    attrs = []
    if oi_kind:
        attrs.append({"key": "openinference.span.kind", "value": {"stringValue": oi_kind}})
    if extra_attrs:
        attrs.extend(extra_attrs)
    return {
        "resourceSpans": [{"resource": {"attributes": []}, "scopeSpans": [{"spans": [{
            "traceId": trace_id, "spanId": "b" * 16, "name": name, "attributes": attrs,
        }]}]}],
    }


def _http_snapshot():
    return TargetSnapshot(
        ref=TargetRef(
            platform_id="test", target_type=TargetType.AGENT,
            external_target_id="agent", external_version_id="v1",
        ),
        display_name="test",
        adapter_type="http",
        adapter_version="1",
    )


def _minimal_dataset():
    from datetime import UTC, datetime

    from agentgate.domain import Case, CaseTurn

    case = Case(id="c1", name="c1", turns=(CaseTurn(id="t1", input={"skill": "test"}),))
    now = datetime.now(UTC)
    return DatasetVersion(
        id="d1-v1", dataset_id="d1", dataset_name="d1", dataset_description="",
        version=1, status=DatasetVersionStatus.PUBLISHED, cases=(case,),
        published_at=now, created_at=now, updated_at=now,
    )


def _dataset_with_tool_expectation():
    from datetime import UTC, datetime

    from agentgate.domain import Case, CaseTurn, Equals, ToolArgumentExpectation

    case = Case(
        id="c1", name="c1",
        turns=(CaseTurn(
            id="t1", input={"skill": "loan_approval", "application_id": "A-1"},
            expectations=(ToolArgumentExpectation(
                id="expect-tool-arg",
                tool="request_human_review", path="human_review",
                condition=Equals(expected=True),
            ),),
        ),),
    )
    now = datetime.now(UTC)
    return DatasetVersion(
        id="d2-v1", dataset_id="d2", dataset_name="d2", dataset_description="",
        version=1, status=DatasetVersionStatus.PUBLISHED, cases=(case,),
        published_at=now, created_at=now, updated_at=now,
    )


class _NoTraceAdapter:
    """Adapter that returns a result with no inline_trace and no OTLP export."""
    adapter_type = "http"
    adapter_version = "1"

    def execute(self, request: TargetExecutionRequest) -> TargetExecutionResult:
        return TargetExecutionResult(
            invocation_id=request.invocation_id,
            output=freeze_json({"message": "degraded"}),
            final_state=freeze_json({}),
            inline_trace=None,
            trace_id="no-otlp-trace",
            completed_at=datetime.now(UTC),
        )


class _ErrorAdapter:
    """Adapter that always raises an invocation error."""
    adapter_type = "http"
    adapter_version = "1"

    def execute(self, request: TargetExecutionRequest) -> TargetExecutionResult:
        raise TargetIntegrationError.unavailable("service down")
