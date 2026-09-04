"""RunEngine tests with the new target snapshot + adapter contract (acceptance #5, #10, #16)."""

from datetime import UTC, datetime

from agentgate.domain import (
    DatasetVersion,
    DatasetVersionStatus,
    TargetRef,
    TargetSnapshot,
    TargetType,
    Trace,
    freeze_json,
)
from agentgate.evaluator import EVALUATORS
from agentgate.run.core import RunEngine
from agentgate.run.targets.http import HttpTargetAdapter
from agentgate.run.targets.python_fn import PythonFunctionTarget
from agentgate.storage.sqlite import SQLiteRepository
from tests.fake_http_agent import FakeHttpAgent


def _http_snapshot(endpoint="http://placeholder"):
    return TargetSnapshot(
        ref=TargetRef(
            platform_id="test", target_type=TargetType.AGENT,
            external_target_id="agent", external_version_id="v1",
        ),
        display_name="test-agent",
        adapter_type="http",
        adapter_version="1",
        invocation_config=freeze_json({"endpoint": endpoint}),
    )


def _python_fn_snapshot(version="loan-agent-v2-fixed"):
    return TargetSnapshot(
        ref=TargetRef(
            platform_id="demo", target_type=TargetType.AGENT,
            external_target_id="loan-agent", external_version_id=version,
        ),
        display_name="loan",
        adapter_type="python_fn",
        adapter_version="1",
    )


def _minimal_dataset():
    from agentgate.domain import Case, CaseTurn
    case = Case(id="c1", name="c1", turns=(CaseTurn(id="t1", input={"skill": "test"}),))
    now = datetime.now(UTC)
    return DatasetVersion(
        id="d1-v1", dataset_id="d1", dataset_name="d1", dataset_description="",
        version=1, status=DatasetVersionStatus.PUBLISHED, cases=(case,),
        published_at=now, created_at=now, updated_at=now,
    )


def test_run_engine_uses_snapshot_no_hardcoded_name(tmp_path):
    repo = SQLiteRepository(tmp_path / "engine.db")
    engine = RunEngine(repo)
    snapshot = _http_snapshot()
    dataset = _minimal_dataset()

    def _stub(run_id, case, version):
        return Trace(
            run_id=run_id, case_id=case.id, spans=(),
            final_output=freeze_json({"version": version}),
        )

    run = engine.run(dataset, snapshot, PythonFunctionTarget(_stub), EVALUATORS)
    assert run.snapshot.target.ref.external_target_id == "agent"
    assert run.snapshot.target.ref.external_version_id == "v1"
    assert run.snapshot.target.adapter_type == "http"
    assert run.status == "completed"


def test_inline_trace_path_skips_otlp_wait(tmp_path):
    repo = SQLiteRepository(tmp_path / "inline.db")
    engine = RunEngine(repo)
    snapshot = _python_fn_snapshot()
    dataset = _minimal_dataset()

    def _stub(run_id, case, version):
        return Trace(
            run_id=run_id, case_id=case.id, spans=(),
            final_output=freeze_json({"ok": True}),
        )

    run = engine.run(
        dataset, snapshot, PythonFunctionTarget(_stub), EVALUATORS,
        trace_wait_seconds=0.1,
    )
    assert run.status == "completed"
    assert not run.trace_warnings
    trace = repo.get_trace(run.id, "c1")
    assert trace is not None


def test_http_end_to_end_with_fake_agent(tmp_path):
    repo = SQLiteRepository(tmp_path / "http-e2e.db")
    engine = RunEngine(repo)
    dataset = _minimal_dataset()

    with FakeHttpAgent(repository=repo, behavior="success") as agent:
        snapshot = _http_snapshot(endpoint=agent.endpoint)
        adapter = HttpTargetAdapter(agent.endpoint)
        run = engine.run(
            dataset, snapshot, adapter, EVALUATORS,
            trace_wait_seconds=5.0, trace_poll_interval_seconds=0.2,
        )

    assert run.status == "completed"
    trace = repo.get_trace(run.id, "c1")
    assert trace is not None
    assert len(trace.spans) == 3
    kinds = {span.kind for span in trace.spans}
    assert "agent" in kinds
    assert "tool" in kinds
    assert trace.status == "complete"
    assert trace.turns[0].completed is True
    assert trace.final_output == {"message": "processed", "status": "approved"}
    assert trace.final_state == {"approved": True, "status": "approved"}
    assert repo.list_results(run.id)
    assert repo.get_latest_evaluated_trace(run.id, "c1") is not None


def test_http_adapter_sends_traceparent_and_correlates(tmp_path):
    repo = SQLiteRepository(tmp_path / "correlation.db")
    engine = RunEngine(repo)
    dataset = _minimal_dataset()

    with FakeHttpAgent(repository=repo, behavior="success") as agent:
        snapshot = _http_snapshot(endpoint=agent.endpoint)
        adapter = HttpTargetAdapter(agent.endpoint)
        run = engine.run(
            dataset, snapshot, adapter, EVALUATORS,
            trace_wait_seconds=5.0, trace_poll_interval_seconds=0.2,
        )

    headers = agent.received_headers[0]
    assert "traceparent" in headers
    assert "idempotency-key" in headers
    assert headers["x-agentgate-run-id"] == run.id
    assert headers["x-agentgate-case-id"] == "c1"

    trace = repo.get_trace(run.id, "c1")
    assert trace is not None
    assert trace.run_id == run.id
    assert trace.case_id == "c1"


def test_http_agent_merges_many_out_of_order_batched_spans_before_evaluation(
    tmp_path,
):
    repo = SQLiteRepository(tmp_path / "many-spans.db")
    engine = RunEngine(repo)
    dataset = _minimal_dataset()

    with FakeHttpAgent(
        repository=repo, behavior="success", extra_span_count=500,
        export_batch_size=73, include_duplicate=True,
    ) as agent:
        snapshot = _http_snapshot(endpoint=agent.endpoint)
        run = engine.run(
            dataset, snapshot, HttpTargetAdapter(agent.endpoint), EVALUATORS,
            trace_wait_seconds=10.0, trace_poll_interval_seconds=0.05,
        )

    trace = repo.get_trace(run.id, "c1")
    assert run.status == "completed"
    assert agent.status_before_terminal == "collecting"
    assert trace is not None and trace.status == "complete"
    assert len(trace.spans) == 503
    assert sum(report.accepted_spans for report in agent.export_reports) == 503
    assert sum(report.duplicate_spans for report in agent.export_reports) == 1
    assert trace.turns[0].completed is True
    assert repo.list_results(run.id)
    assert repo.get_latest_evaluated_trace(run.id, "c1") == trace
