import sqlite3
from datetime import timedelta

import pytest

from agentgate.control_plane import EvaluationService
from agentgate.domain import TraceCompletenessPolicy
from agentgate.storage.sqlite import SQLiteRepository
from agentgate.trace.normalizer import normalize_otlp_json
from agentgate.trace.receivers.otlp_http import ingest_otlp_http_json


def _payload(run_id, span_id, *, parent=None, complete=False):
    span = {
        "traceId": "e" * 32,
        "spanId": span_id,
        "name": span_id,
        "startTimeUnixNano": "100",
        "endTimeUnixNano": "200",
        "attributes": [
            {"key": "agentgate.trace.complete", "value": {"boolValue": complete}},
        ],
    }
    if parent:
        span["parentSpanId"] = parent
    return {"resourceSpans": [{"resource": {"attributes": [
        {"key": "agentgate.run.id", "value": {"stringValue": run_id}},
        {"key": "agentgate.case.id", "value": {"stringValue": "high-risk-approval"}},
    ]}, "scopeSpans": [{"spans": [span]}]}]}


def test_reconstruction_is_stable_across_arrival_order_and_restart(tmp_path):
    first_repo = SQLiteRepository(tmp_path / "first.db")
    second_repo = SQLiteRepository(tmp_path / "second.db")
    run = EvaluationService(first_repo).launch("loan-agent-v2-fixed")
    EvaluationService(second_repo)
    second_repo.save_run(run)
    root_id = "1" * 16
    child_id = "2" * 16

    ingest_otlp_http_json(_payload(run.id, root_id), first_repo)
    ingest_otlp_http_json(
        _payload(run.id, child_id, parent=root_id, complete=True), first_repo
    )
    ingest_otlp_http_json(
        _payload(run.id, child_id, parent=root_id, complete=True), second_repo
    )
    ingest_otlp_http_json(_payload(run.id, root_id), second_repo)

    first = first_repo.get_trace(run.id, "high-risk-approval")
    second = second_repo.get_trace(run.id, "high-risk-approval")
    assert first is not None and second is not None
    assert [span.source_span_id for span in first.spans] == [root_id, child_id]
    assert first.content_sha256 == second.content_sha256
    assert first.id == second.id

    reopened = SQLiteRepository(tmp_path / "first.db")
    restored = reopened.get_trace(run.id, "high-risk-approval")
    assert restored == first
    assert reopened.get_trace_revision(run.id, "high-risk-approval", 1) is not None


def test_old_mutable_trace_schema_is_rejected(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE traces (id TEXT PRIMARY KEY, run_id TEXT, case_id TEXT, payload TEXT)"
        )
    with pytest.raises(RuntimeError, match="unsupported P1 Trace schema"):
        SQLiteRepository(path)


def test_intermediate_trace_schema_version_is_rejected(tmp_path):
    path = tmp_path / "intermediate.db"
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE agentgate_schema (component TEXT PRIMARY KEY, version INTEGER)"
        )
        db.execute("INSERT INTO agentgate_schema VALUES('trace', 2)")
        db.execute(
            "CREATE TABLE traces (id TEXT PRIMARY KEY, run_id TEXT, case_id TEXT, payload TEXT)"
        )
        db.execute("CREATE TABLE trace_records (revision INTEGER)")
    with pytest.raises(RuntimeError, match="unsupported P1 Trace schema"):
        SQLiteRepository(path)


def _with_policy(repository, run, **updates):
    policy = TraceCompletenessPolicy(**updates)
    snapshot = run.snapshot.model_copy(update={
        "trace_policy": policy, "snapshot_sha256": "",
    })
    changed = run.model_copy(update={"snapshot": snapshot})
    repository.save_run(changed)
    return repository.get_run(run.id)


def _terminal_payload(run_id, span_id="3" * 16, *, output="done"):
    payload = _payload(run_id, span_id, complete=True)
    attrs = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["attributes"]
    attrs.extend([
        {"key": "agentgate.turn.id", "value": {
            "stringValue": "high-risk-turn-1"
        }},
        {"key": "agentgate.turn.complete", "value": {"boolValue": True}},
        {"key": "agentgate.final.output", "value": {"stringValue": output}},
        {"key": "agentgate.final.state", "value": {"kvlistValue": {"values": [
            {"key": "status", "value": {"stringValue": "done"}},
        ]}}},
    ])
    return payload


def test_deadline_creates_one_incomplete_revision_and_duplicate_is_stable(tmp_path):
    repository = SQLiteRepository(tmp_path / "deadline.db")
    run = EvaluationService(repository).launch("loan-agent-v2-fixed")
    run = _with_policy(repository, run, deadline_seconds=1)
    batch = normalize_otlp_json(_payload(run.id, "4" * 16))
    first = repository.ingest_trace_batch(batch)
    assert first.accepted_spans == 1
    collecting = repository.get_trace(run.id, "high-risk-approval")
    assert collecting.status == "collecting" and collecting.revision == 1

    before = repository.expire_trace(
        run.id, "high-risk-approval", run.started_at + timedelta(milliseconds=500)
    )
    assert before.revision == 1
    expired = repository.expire_trace(
        run.id, "high-risk-approval", run.started_at + timedelta(seconds=2)
    )
    assert expired.status == "incomplete" and expired.revision == 2
    repeated = repository.expire_trace(
        run.id, "high-risk-approval", run.started_at + timedelta(seconds=3)
    )
    assert repeated.revision == 2

    duplicate = repository.ingest_trace_batch(batch.model_copy(update={
        "id": "duplicate-batch", "received_at": run.started_at + timedelta(seconds=4),
    }))
    assert duplicate.duplicate_spans == 1
    assert repository.get_trace(run.id, "high-risk-approval").revision == 2


def test_evaluated_trace_gets_late_revision_or_rejects_by_policy(tmp_path):
    repository = SQLiteRepository(tmp_path / "late.db")
    run = EvaluationService(repository).launch("loan-agent-v2-fixed")
    report = repository.ingest_trace_batch(
        normalize_otlp_json(_terminal_payload(run.id))
    )
    assert report.accepted_signals == 4
    revision_one = repository.get_trace(run.id, "high-risk-approval")
    result = repository.list_results(run.id)[0].model_copy(update={
        "trace_revision": revision_one.revision,
        "trace_content_sha256": revision_one.content_sha256,
    })
    repository.save_results([result])
    assert repository.get_latest_evaluated_trace(
        run.id, "high-risk-approval"
    ).revision == 1

    ingest_otlp_http_json(_payload(run.id, "5" * 16), repository)
    latest = repository.get_trace(run.id, "high-risk-approval")
    metadata = repository.get_trace_revision_metadata(run.id, "high-risk-approval", 2)
    assert latest.revision == 2
    assert metadata["late_arrival"] == 1 and metadata["supersedes_revision"] == 1
    assert repository.has_unevaluated_trace_revision(run.id, "high-risk-approval")

    rejecting = SQLiteRepository(tmp_path / "reject.db")
    reject_run = EvaluationService(rejecting).launch("loan-agent-v2-fixed")
    reject_run = _with_policy(rejecting, reject_run, late_arrival_policy="reject")
    ingest_otlp_http_json(_terminal_payload(reject_run.id), rejecting)
    evaluated = rejecting.get_trace(reject_run.id, "high-risk-approval")
    reject_result = rejecting.list_results(reject_run.id)[0].model_copy(update={
        "trace_revision": evaluated.revision,
        "trace_content_sha256": evaluated.content_sha256,
    })
    rejecting.save_results([reject_result])
    rejected = ingest_otlp_http_json(_payload(reject_run.id, "6" * 16), rejecting)
    assert rejected.rejected_spans == 1
    assert "late telemetry rejected" in rejected.errors[0]
    assert rejecting.get_trace(reject_run.id, "high-risk-approval").revision == 1


def test_quiet_period_uses_last_new_evidence_not_duplicate_time(tmp_path):
    repository = SQLiteRepository(tmp_path / "quiet.db")
    run = EvaluationService(repository).launch("loan-agent-v2-fixed")
    run = _with_policy(repository, run, quiet_period_ms=1000)
    received = run.started_at
    batch = normalize_otlp_json(_terminal_payload(run.id)).model_copy(update={
        "received_at": received,
    })
    repository.ingest_trace_batch(batch)
    first = repository.get_trace(run.id, "high-risk-approval")
    assert first.status == "collecting" and first.revision == 1

    duplicate = batch.model_copy(update={
        "id": "quiet-duplicate", "received_at": received + timedelta(milliseconds=900),
    })
    repository.ingest_trace_batch(duplicate)
    completed = repository.evaluate_trace_completeness(
        run.id, "high-risk-approval", received + timedelta(milliseconds=1100)
    )
    assert completed.status == "complete" and completed.revision == 2
    metadata = repository.get_trace_revision_metadata(
        run.id, "high-risk-approval", completed.revision
    )
    assert metadata["last_evidence_at"] == received.isoformat()
