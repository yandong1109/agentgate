"""HTTP target adapter tests against a fake external HTTP platform (acceptance #6-9, #16)."""

import pytest

from agentgate.domain import (
    TargetExecutionRequest,
    TargetRef,
    TargetSnapshot,
    TargetType,
    freeze_json,
)
from agentgate.run.targets.base import EnvCredentialResolver, TargetIntegrationError
from agentgate.run.targets.http import HttpTargetAdapter
from tests.fake_http_agent import FakeHttpAgent


def _snapshot(credential_ref=None):
    return TargetSnapshot(
        ref=TargetRef(
            platform_id="test", target_type=TargetType.AGENT,
            external_target_id="agent", external_version_id="v1",
        ),
        display_name="test-agent",
        adapter_type="http",
        adapter_version="1",
        invocation_config=freeze_json({"endpoint": "http://placeholder"}),
        credential_ref=credential_ref,
    )


def _request(snapshot, run_id="run", case_id="case"):
    return TargetExecutionRequest(
        invocation_id="inv-1",
        idempotency_key="key-1",
        run_id=run_id,
        case_id=case_id,
        target=snapshot,
        input=freeze_json({"turns": [{"turn_id": "t1", "input": {"skill": "test"}}]}),
        state=freeze_json({}),
        timeout_seconds=5.0,
        traceparent="00-" + "a" * 32 + "-" + "b" * 16 + "-01",
    )


def test_http_adapter_invokes_exact_version_and_returns_result():
    with FakeHttpAgent(behavior="success") as agent:
        snapshot = _snapshot()
        adapter = HttpTargetAdapter(agent.endpoint)
        result = adapter.execute(_request(snapshot))
    assert result.invocation_id == "inv-1"
    assert result.output == {"message": "processed", "status": "approved"}
    assert result.final_state == {"approved": True, "status": "approved"}
    assert result.inline_trace is None
    assert result.trace_id is not None


def test_http_adapter_sends_required_headers():
    with FakeHttpAgent(behavior="success") as agent:
        adapter = HttpTargetAdapter(agent.endpoint)
        adapter.execute(_request(_snapshot()))
    headers = agent.received_headers[0]
    assert headers.get("traceparent") == "00-" + "a" * 32 + "-" + "b" * 16 + "-01"
    assert headers.get("idempotency-key") == "key-1"
    assert headers.get("x-agentgate-run-id") == "run"
    assert headers.get("x-agentgate-case-id") == "case"
    assert headers.get("content-type") == "application/json"


def test_http_adapter_flattens_single_turn_envelope():
    """A single-turn Case must reach the wire as the documented flat Invoke contract."""
    with FakeHttpAgent(behavior="success") as agent:
        adapter = HttpTargetAdapter(agent.endpoint)
        adapter.execute(_request(_snapshot()))
    body = agent.received_bodies[0]
    assert body["input"] == {"skill": "test"}
    assert body["turn_id"] == "t1"
    assert agent.received_headers[0].get("x-agentgate-turn-id") == "t1"


def test_http_adapter_keeps_multi_turn_envelope_on_wire():
    with FakeHttpAgent(behavior="success") as agent:
        adapter = HttpTargetAdapter(agent.endpoint)
        request = _request(_snapshot()).model_copy(update={"input": freeze_json({
            "turns": [
                {"turn_id": "t1", "input": {"skill": "a"}},
                {"turn_id": "t2", "input": {"skill": "b"}},
            ],
        })})
        adapter.execute(request)
    body = agent.received_bodies[0]
    assert body["turn_id"] is None
    assert [t["turn_id"] for t in body["input"]["turns"]] == ["t1", "t2"]


def test_http_adapter_passes_flat_input_through_unchanged():
    with FakeHttpAgent(behavior="success") as agent:
        adapter = HttpTargetAdapter(agent.endpoint)
        request = _request(_snapshot()).model_copy(update={
            "input": freeze_json({"question": "hello"}),
            "turn_id": "t9",
        })
        adapter.execute(request)
    body = agent.received_bodies[0]
    assert body["input"] == {"question": "hello"}
    assert body["turn_id"] == "t9"
    assert agent.received_headers[0].get("x-agentgate-turn-id") == "t9"


def test_http_adapter_accepts_title_case_content_type():
    """Header lookups must be case-insensitive (real agents send ``Content-Type``)."""
    with FakeHttpAgent(behavior="success_title_case") as agent:
        adapter = HttpTargetAdapter(agent.endpoint)
        result = adapter.execute(_request(_snapshot()))
    assert result.output == {"message": "processed", "status": "approved"}


def test_http_adapter_401_maps_to_unauthorized():
    with FakeHttpAgent(behavior="401") as agent:
        adapter = HttpTargetAdapter(agent.endpoint)
        with pytest.raises(TargetIntegrationError, match="unauthorized"):
            adapter.execute(_request(_snapshot()))


def test_http_adapter_404_maps_to_target_not_found():
    with FakeHttpAgent(behavior="404") as agent:
        adapter = HttpTargetAdapter(agent.endpoint)
        with pytest.raises(TargetIntegrationError, match="target_not_found"):
            adapter.execute(_request(_snapshot()))


def test_http_adapter_429_maps_to_rate_limited():
    with FakeHttpAgent(behavior="429") as agent:
        adapter = HttpTargetAdapter(agent.endpoint)
        with pytest.raises(TargetIntegrationError, match="rate_limited"):
            adapter.execute(_request(_snapshot()))


def test_http_adapter_500_maps_to_unavailable():
    with FakeHttpAgent(behavior="500") as agent:
        adapter = HttpTargetAdapter(agent.endpoint)
        with pytest.raises(TargetIntegrationError, match="unavailable"):
            adapter.execute(_request(_snapshot()))


def test_http_adapter_timeout_maps_to_timeout_error():
    with FakeHttpAgent(behavior="slow") as agent:
        adapter = HttpTargetAdapter(agent.endpoint)
        request = _request(_snapshot())
        request = request.model_copy(update={"timeout_seconds": 0.5})
        with pytest.raises(TargetIntegrationError, match="timeout"):
            adapter.execute(request)


def test_http_adapter_redacts_authorization_in_errors():
    import os
    os.environ["TEST_SECRET_KEY"] = "Bearer super-secret-value"
    try:
        with FakeHttpAgent(behavior="401") as agent:
            resolver = EnvCredentialResolver()
            adapter = HttpTargetAdapter(agent.endpoint, resolver)
            snapshot = _snapshot(credential_ref="TEST_SECRET_KEY")
            with pytest.raises(TargetIntegrationError) as exc_info:
                adapter.execute(_request(snapshot))
            assert "super-secret-value" not in str(exc_info.value)
    finally:
        del os.environ["TEST_SECRET_KEY"]


def test_redact_strips_bearer_token_value():
    from agentgate.run.targets.http import _redact

    redacted = _redact("Authorization: Bearer secret123")
    assert "secret123" not in redacted
    assert "[redacted]" in redacted


def test_http_adapter_rejects_non_json_content_type():
    with FakeHttpAgent(behavior="bad_content_type") as agent:
        adapter = HttpTargetAdapter(agent.endpoint)
        with pytest.raises(TargetIntegrationError, match="protocol_error"):
            adapter.execute(_request(_snapshot()))


def test_http_adapter_rejects_missing_response_fields():
    with FakeHttpAgent(behavior="missing_fields") as agent:
        adapter = HttpTargetAdapter(agent.endpoint)
        with pytest.raises(TargetIntegrationError, match="protocol_error"):
            adapter.execute(_request(_snapshot()))
