import gzip
import json

from fastapi.testclient import TestClient
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest, ExportTraceServiceResponse,
)
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

from agentgate.server.application import create_app


def test_api_evaluation_and_persisted_trace(tmp_path):
    with TestClient(create_app(tmp_path / "api.db")) as client:
        response = client.post("/api/evaluations", json={
            "version": "loan-agent-v1-risky",
            "dataset_id": "loan-risk-policy",
            "dataset_version": 1,
        })
        assert response.status_code == 201
        run_id = response.json()["id"]
        report = client.get(f"/api/runs/{run_id}").json()
        assert report["gate"]["outcome"] == "fail"
        trace = client.get(f"/api/runs/{run_id}/traces/high-risk-approval")
        assert trace.status_code == 200
        assert any(span["name"] == "approve_loan" for span in trace.json()["spans"])


def test_api_launch_requires_an_explicit_dataset_version(tmp_path):
    with TestClient(create_app(tmp_path / "explicit-version.db")) as client:
        response = client.post("/api/evaluations", json={
            "version": "loan-agent-v2-fixed",
            "dataset_id": "loan-risk-policy",
        })
        assert response.status_code == 422


def test_otlp_http_uses_post_and_health_is_separate(tmp_path):
    with TestClient(create_app(tmp_path / "otlp.db")) as client:
        run_id = client.post("/api/evaluations", json={
            "version": "loan-agent-v2-fixed", "dataset_id": "loan-risk-policy",
            "dataset_version": 1,
        }).json()["id"]
        payload = {"resourceSpans": [{"resource": {"attributes": [
            {"key": "agentgate.run.id", "value": {"stringValue": run_id}},
            {"key": "agentgate.case.id", "value": {"stringValue": "high-risk-approval"}},
        ]}, "scopeSpans": [{"spans": [{
            "traceId": "a" * 32, "spanId": "b" * 16, "name": "tool.call",
            "attributes": [{"key": "agentgate.span.kind",
                            "value": {"stringValue": "tool"}}],
        }]}]}]}
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/v1/traces").status_code == 405
        response = client.post("/v1/traces", json=payload)
        assert response.status_code == 200
        assert response.json()["accepted_spans"] == 1
        stored = client.app.state.repository.get_trace(run_id, "high-risk-approval")
        assert stored is not None and stored.spans[0].name == "tool.call"


def test_otlp_http_protobuf_and_request_limit(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path / "otlp-protobuf.db")) as client:
        run_id = client.post("/api/evaluations", json={
            "version": "loan-agent-v2-fixed", "dataset_id": "loan-risk-policy",
            "dataset_version": 1,
        }).json()["id"]
        attrs = [
            KeyValue(key="agentgate.run.id", value=AnyValue(string_value=run_id)),
            KeyValue(key="agentgate.case.id", value=AnyValue(
                string_value="high-risk-approval"
            )),
            KeyValue(key="agentgate.trace.complete", value=AnyValue(bool_value=True)),
        ]
        request = ExportTraceServiceRequest(resource_spans=[ResourceSpans(
            resource=Resource(attributes=attrs),
            scope_spans=[ScopeSpans(spans=[Span(
                trace_id=bytes.fromhex("c" * 32),
                span_id=bytes.fromhex("d" * 16),
                name="protobuf-span",
                start_time_unix_nano=100,
                end_time_unix_nano=200,
            )])],
        )])
        response = client.post(
            "/v1/traces", content=request.SerializeToString(),
            headers={"content-type": "application/x-protobuf"},
        )
        assert response.status_code == 200
        ExportTraceServiceResponse.FromString(response.content)
        trace = client.app.state.repository.get_trace(run_id, "high-risk-approval")
        assert trace is not None and trace.spans[0].name == "protobuf-span"

        monkeypatch.setenv("AGENTGATE_OTLP_MAX_REQUEST_BYTES", "2")
        too_large = client.post(
            "/v1/traces", content=request.SerializeToString(),
            headers={"content-type": "application/x-protobuf"},
        )
        assert too_large.status_code == 413


def test_otlp_http_gzip_and_content_encoding_validation(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path / "otlp-gzip.db")) as client:
        run_id = client.post("/api/evaluations", json={
            "version": "loan-agent-v2-fixed", "dataset_id": "loan-risk-policy",
            "dataset_version": 1,
        }).json()["id"]
        payload = {"resourceSpans": [{"resource": {"attributes": [
            {"key": "agentgate.run.id", "value": {"stringValue": run_id}},
            {"key": "agentgate.case.id", "value": {
                "stringValue": "high-risk-approval"
            }},
        ]}, "scopeSpans": [{"spans": [{
            "traceId": "9" * 32, "spanId": "8" * 16, "name": "gzip-span",
        }]}]}]}
        encoded = gzip.compress(json.dumps(payload).encode())
        accepted = client.post("/v1/traces", content=encoded, headers={
            "content-type": "application/json", "content-encoding": "gzip",
        })
        assert accepted.status_code == 200
        assert accepted.json()["accepted_spans"] == 1

        unsupported = client.post("/v1/traces", content=b"x", headers={
            "content-type": "application/json", "content-encoding": "br",
        })
        assert unsupported.status_code == 415

        malformed = client.post("/v1/traces", content=b"not-gzip", headers={
            "content-type": "application/json", "content-encoding": "gzip",
        })
        assert malformed.status_code == 422

        monkeypatch.setenv("AGENTGATE_OTLP_MAX_DECOMPRESSED_BYTES", "4")
        oversized = client.post("/v1/traces", content=encoded, headers={
            "content-type": "application/json", "content-encoding": "gzip",
        })
        assert oversized.status_code == 422


def test_invalid_otlp_protobuf_is_a_client_error(tmp_path):
    with TestClient(create_app(tmp_path / "invalid-protobuf.db")) as client:
        response = client.post(
            "/v1/traces", content=b"\xff\xff\xff",
            headers={"content-type": "application/x-protobuf"},
        )
        assert response.status_code == 422
        assert "invalid OTLP protobuf" in response.json()["detail"]
