from agentgate.case import DatasetService
from agentgate.control_plane import EvaluationService
from agentgate.domain import (
    Case,
    CaseTurn,
    Equals,
    MatchesPattern,
    OutputExpectation,
    StateExpectation,
)
from agentgate.storage.sqlite import SQLiteRepository
from agentgate.trace.receivers.otlp_http import ingest_otlp_http_json


def test_multi_turn_session_produces_turn_aware_trace_and_checks(tmp_path):
    repository = SQLiteRepository(tmp_path / "multi.db")
    datasets = DatasetService(repository)
    dataset = datasets.create_dataset("Multi-turn")
    datasets.create_draft(dataset.id)
    datasets.save_case(dataset.id, Case(
        id="multi-case",
        name="Collect then approve",
        turns=(
            CaseTurn(
                id="collect",
                input={"skill": "loan_approval"},
                expected_skill="loan_approval",
                expectations=(OutputExpectation(
                    id="ask-fields",
                    path="message",
                    condition=MatchesPattern(pattern="请补充"),
                ),),
            ),
            CaseTurn(
                id="decide",
                input={"application_id": "M-1", "risk": "high", "amount": 50000},
                expected_skill="loan_approval",
                expectations=(StateExpectation(
                    id="review-state",
                    path="status",
                    condition=Equals(expected="pending_review"),
                ),),
                required_tools=("credit_inquiry", "request_human_review"),
                forbidden_tools=("approve_loan",),
                policy_rules=("high_risk_requires_review",),
            ),
        ),
    ))
    version = datasets.publish_draft(dataset.id)

    service = EvaluationService(repository)
    run = service.launch(
        "loan-agent-v2-fixed", dataset.id, version.version
    )
    trace = repository.get_trace(run.id, "multi-case")
    assert [item.turn_id for item in trace.turns] == ["collect", "decide"]
    assert {span.attributes["turn_id"] for span in trace.spans} == {"collect", "decide"}
    report = service.run_detail(run.id)
    output = next(item for item in report.results if item.evaluator_id == "final-output")
    state = next(item for item in report.results if item.evaluator_id == "final-state")
    assert output.checks[0].turn_id == "collect"
    assert state.checks[0].turn_id == "decide"
    assert report.gate.outcome == "pass"


def _signal_span(span_id, turn_id, output, *, terminal=False, invocation=None):
    attrs = [
        {"key": "agentgate.turn.id", "value": {"stringValue": turn_id}},
        {"key": "agentgate.turn.complete", "value": {"boolValue": True}},
        {"key": "agentgate.final.output", "value": {"stringValue": output}},
        {"key": "agentgate.final.state", "value": {"kvlistValue": {"values": [
            {"key": "turn", "value": {"stringValue": turn_id}},
        ]}}},
    ]
    if terminal:
        attrs.append({"key": "agentgate.trace.complete", "value": {"boolValue": True}})
    if invocation:
        attrs.append({"key": "agentgate.invocation.id", "value": {
            "stringValue": invocation
        }})
    return {
        "traceId": ("a" if turn_id == "collect" else "b") * 32,
        "spanId": span_id, "name": turn_id,
        "startTimeUnixNano": "100", "endTimeUnixNano": "200",
        "attributes": attrs,
    }


def test_otlp_reconstruction_builds_ordered_multi_turns_and_semantic_conflicts(tmp_path):
    repository = SQLiteRepository(tmp_path / "multi-otlp.db")
    datasets = DatasetService(repository)
    dataset = datasets.create_dataset("Multi-turn OTLP")
    datasets.create_draft(dataset.id)
    datasets.save_case(dataset.id, Case(
        id="multi-case", name="Two turns",
        turns=(
            CaseTurn(id="collect", input={"message": "start"}),
            CaseTurn(id="decide", input={"message": "finish"}),
        ),
    ))
    version = datasets.publish_draft(dataset.id)
    run = EvaluationService(repository).launch(
        "loan-agent-v2-fixed", dataset.id, version.version
    )
    resource_attrs = [
        {"key": "agentgate.run.id", "value": {"stringValue": run.id}},
        {"key": "agentgate.case.id", "value": {"stringValue": "multi-case"}},
    ]
    payload = {"resourceSpans": [{"resource": {"attributes": resource_attrs},
        "scopeSpans": [{"spans": [
            _signal_span("1" * 16, "collect", "need-details", invocation="inv-b"),
            _signal_span("2" * 16, "decide", "review", terminal=True, invocation="inv-a"),
        ]}]}]}
    ingest_otlp_http_json(payload, repository)
    trace = repository.get_trace(run.id, "multi-case")
    assert trace.status == "complete"
    assert [turn.turn_id for turn in trace.turns] == ["collect", "decide"]
    assert [turn.input["message"] for turn in trace.turns] == ["start", "finish"]
    assert trace.turns[1].invocation_ids == ("inv-a",)
    assert trace.final_output == "review"

    # A second source span carrying the same authoritative value agrees.
    agreeing = {"resourceSpans": [{"resource": {"attributes": resource_attrs},
        "scopeSpans": [{"spans": [
            _signal_span("3" * 16, "decide", "review", terminal=True),
        ]}]}]}
    ingest_otlp_http_json(agreeing, repository)
    assert repository.get_trace(run.id, "multi-case").conflict_count == 0

    conflicting = {"resourceSpans": [{"resource": {"attributes": resource_attrs},
        "scopeSpans": [{"spans": [
            _signal_span("4" * 16, "decide", "approve", terminal=True),
        ]}]}]}
    ingest_otlp_http_json(conflicting, repository)
    trace = repository.get_trace(run.id, "multi-case")
    conflicts = repository.list_trace_conflicts(run.id, "multi-case")
    assert trace.status == "conflicted"
    assert trace.conflict_count == len(conflicts) == 1
    assert conflicts[0]["kind"] == "semantic_signal"


def test_multi_turn_otlp_rejects_span_without_turn_id(tmp_path):
    repository = SQLiteRepository(tmp_path / "multi-missing-turn.db")
    datasets = DatasetService(repository)
    dataset = datasets.create_dataset("Missing turn")
    datasets.create_draft(dataset.id)
    datasets.save_case(dataset.id, Case(
        id="multi-case", name="Two turns",
        turns=(
            CaseTurn(id="one", input={"message": "one"}),
            CaseTurn(id="two", input={"message": "two"}),
        ),
    ))
    version = datasets.publish_draft(dataset.id)
    run = EvaluationService(repository).launch(
        "loan-agent-v2-fixed", dataset.id, version.version
    )
    payload = {"resourceSpans": [{"resource": {"attributes": [
        {"key": "agentgate.run.id", "value": {"stringValue": run.id}},
        {"key": "agentgate.case.id", "value": {"stringValue": "multi-case"}},
    ]}, "scopeSpans": [{"spans": [{
        "traceId": "c" * 32, "spanId": "7" * 16, "name": "unassigned",
    }]}]}]}
    report = ingest_otlp_http_json(payload, repository)
    assert report.accepted_spans == 0 and report.rejected_spans == 1
    assert "multi-turn case requires turn_id" in report.errors[0]
