"""Integration tests for the POST /api/json-schema/validate precheck endpoint."""

import pytest
from fastapi.testclient import TestClient

from agentgate.domain.base import canonical_json
from agentgate.evaluator import validation as evaluator_validation
from agentgate.server.application import create_app


def _schema_of_size(target_bytes: int) -> dict:
    base = {"type": "string", "description": ""}
    base_size = len(canonical_json(base).encode("utf-8"))
    return {"type": "string", "description": "x" * (target_bytes - base_size)}


def _schema_of_depth(depth: int) -> dict:
    schema = {"type": "string"}
    cur = schema
    for _ in range(depth - 1):
        inner = {"type": "string"}
        cur["nested"] = inner
        cur = inner
    return schema


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "schema-api.db")) as c:
        yield c


def test_valid_schema_returns_200_true(client):
    r = client.post("/api/json-schema/validate", json={"json_schema": {"type": "string"}})
    assert r.status_code == 200
    assert r.json() == {"valid": True}


def test_valid_schema_passed_as_json_text_string(client):
    r = client.post("/api/json-schema/validate", json={"json_schema": '{"type":"string"}'})
    assert r.status_code == 200
    assert r.json() == {"valid": True}


@pytest.mark.parametrize("schema, expected_code, expected_keys", [
    ({"$schema": "http://json-schema.org/draft-07/schema#", "type": "string"},
     "unsupported_draft", {"declared"}),
    ({"$ref": "https://example.com/x.json"},
     "remote_ref_forbidden", {"ref"}),
    ({"type": "not_a_real_type"},
     "invalid_schema", set()),
    (_schema_of_size(evaluator_validation._MAX_SERIALIZED_SIZE + 1),
     "size_exceeded", {"limit", "actual"}),
    (_schema_of_depth(evaluator_validation._MAX_DEPTH + 1),
     "depth_exceeded", {"limit", "actual"}),
])
def test_failure_codes_return_200_with_structured_errors(
    client, schema, expected_code, expected_keys,
):
    r = client.post("/api/json-schema/validate", json={
        "json_schema": schema, "instance_mode": "structured",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    errors = body["errors"]
    assert len(errors) == 1
    issue = errors[0]
    assert issue["code"] == expected_code
    assert "message" in issue
    assert expected_keys.issubset(issue.keys())


def test_input_parse_error_for_invalid_json_text(client):
    r = client.post("/api/json-schema/validate", json={"json_schema": "not valid json {"})
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    assert body["errors"][0]["code"] == "input_parse_error"
    assert "message" in body["errors"][0]


def test_missing_json_schema_field_returns_422(client):
    r = client.post("/api/json-schema/validate", json={"instance_mode": "structured"})
    assert r.status_code == 422


def test_instance_mode_is_passed_through_to_service(client, monkeypatch):
    captured = {}

    def fake_validate(json_schema, instance_mode="structured"):
        captured["json_schema"] = json_schema
        captured["instance_mode"] = instance_mode
        return {"valid": True}

    monkeypatch.setattr(client.app.state.service, "validate_json_schema", fake_validate)
    r = client.post("/api/json-schema/validate", json={
        "json_schema": {"type": "string"}, "instance_mode": "json_text",
    })
    assert r.status_code == 200
    assert r.json() == {"valid": True}
    assert captured["json_schema"] == {"type": "string"}
    assert captured["instance_mode"] == "json_text"


def test_endpoint_delegates_to_service_and_returns_its_response(client, monkeypatch):
    # If the endpoint inlined validation rules, it would not call the service
    # method and the spy would never record the call.
    captured = {}

    def fake_validate(json_schema, instance_mode="structured"):
        captured["called"] = True
        captured["json_schema"] = json_schema
        captured["instance_mode"] = instance_mode
        return {"valid": False, "errors": [{"code": "invalid_schema", "message": "stub"}]}

    monkeypatch.setattr(client.app.state.service, "validate_json_schema", fake_validate)
    r = client.post("/api/json-schema/validate", json={"json_schema": {"type": "string"}})
    assert r.status_code == 200
    assert captured.get("called") is True
    assert captured["json_schema"] == {"type": "string"}
    assert captured["instance_mode"] == "structured"
    assert r.json() == {"valid": False, "errors": [{"code": "invalid_schema", "message": "stub"}]}
