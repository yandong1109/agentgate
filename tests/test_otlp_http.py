from agentgate.control_plane import EvaluationService
from agentgate.storage.sqlite import SQLiteRepository
from agentgate.trace.receivers.otlp_http import ingest_otlp_http_json

TRACE_ID = "0123456789abcdef0123456789abcdef"
SPAN_ID = "0123456789abcdef"


def _payload(
    run_id: str, *, name: str = "route", complete: bool = False,
    include_outcome: bool = False,
):
    outcome = []
    if include_outcome:
        outcome = [
            {"key": "agentgate.final.output", "value": {"kvlistValue": {"values": [
                {"key": "answer", "value": {"stringValue": "approved"}},
            ]}}},
            {"key": "agentgate.final.state", "value": {"kvlistValue": {"values": [
                {"key": "status", "value": {"stringValue": "done"}},
            ]}}},
        ]
    return {"resourceSpans": [{"resource": {"attributes": [
        {"key": "agentgate.run.id", "value": {"stringValue": run_id}},
        {"key": "agentgate.case.id", "value": {"stringValue": "high-risk-approval"}},
    ]}, "scopeSpans": [{"spans": [{
        "traceId": TRACE_ID, "spanId": SPAN_ID, "name": name,
        "startTimeUnixNano": "100", "endTimeUnixNano": "200",
        "attributes": [
            {"key": "agentgate.span.kind", "value": {"stringValue": "routing"}},
            {"key": "agentgate.turn.id", "value": {"stringValue": "high-risk-turn-1"}},
            {"key": "agentgate.trace.complete", "value": {"boolValue": complete}},
            {"key": "agentgate.turn.complete", "value": {"boolValue": complete}},
            {"key": "selected_skill", "value": {"stringValue": "loan_approval"}},
            *outcome,
        ],
    }]}]}]}


def test_receiver_merges_duplicate_and_conflicting_otlp_json(tmp_path):
    repository = SQLiteRepository(tmp_path / "receiver.db")
    run = EvaluationService(repository).launch("loan-agent-v2-fixed")
    first = ingest_otlp_http_json(_payload(run.id), repository)
    duplicate = ingest_otlp_http_json(_payload(run.id), repository)
    conflict = ingest_otlp_http_json(_payload(run.id, name="changed"), repository)
    assert first.accepted_spans == 1
    assert duplicate.duplicate_spans == 1
    assert conflict.conflicted_spans == 1
    trace = repository.get_trace(run.id, "high-risk-approval")
    assert trace is not None
    assert trace.spans[0].name == "route"
    assert trace.status == "conflicted"


def test_receiver_rejects_bad_source_ids(tmp_path):
    repository = SQLiteRepository(tmp_path / "receiver.db")
    invalid_ids = _payload("missing-run")
    invalid_ids["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["traceId"] = "bad"
    report = ingest_otlp_http_json(invalid_ids, repository)
    assert report.accepted_spans == 0
    assert report.rejected_spans == 1
    assert "traceId" in report.errors[0]


def test_receiver_rejects_target_identity_mismatch(tmp_path):
    repository = SQLiteRepository(tmp_path / "target-mismatch.db")
    run = EvaluationService(repository).launch("loan-agent-v2-fixed")
    payload = _payload(run.id, complete=True, include_outcome=True)
    attributes = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0][
        "attributes"
    ]
    attributes.append({
        "key": "agentgate.target.version",
        "value": {"stringValue": "wrong-version"},
    })
    report = ingest_otlp_http_json(payload, repository)
    assert report.accepted_spans == 0 and report.rejected_spans == 1
    assert report.accepted_signals == 0
    assert "does not match TargetSnapshot" in report.errors[0]


def test_terminal_marker_completes_trace(tmp_path):
    repository = SQLiteRepository(tmp_path / "receiver.db")
    run = EvaluationService(repository).launch("loan-agent-v2-fixed")
    report = ingest_otlp_http_json(
        _payload(run.id, complete=True, include_outcome=True), repository
    )
    trace = repository.get_trace(run.id, "high-risk-approval")
    assert report.accepted_spans == 1
    assert trace is not None and trace.status == "complete"
    assert trace.final_output_present and trace.final_output["answer"] == "approved"
    assert trace.final_state_present and trace.final_state["status"] == "done"
