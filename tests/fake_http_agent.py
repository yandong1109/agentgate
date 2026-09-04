"""In-process fake HTTP Agent fixture for HTTP adapter + OTel correlation tests."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from uuid import uuid4


class FakeHttpAgent:
    """A minimal HTTP Agent that responds to POST /invoke and exports OTLP."""

    def __init__(
        self, repository=None, *, behavior: str = "success",
        trace_export: bool = True, extra_span_count: int = 0,
        export_batch_size: int = 100, include_duplicate: bool = False,
        port: int = 0,
    ) -> None:
        self.repository = repository
        self.behavior = behavior
        self.trace_export = trace_export
        self.extra_span_count = extra_span_count
        self.export_batch_size = export_batch_size
        self.include_duplicate = include_duplicate
        self.received_headers: list[dict[str, str]] = []
        self.received_bodies: list[dict[str, Any]] = []
        self.exported_trace_ids: list[str] = []
        self.export_reports = []
        self.status_before_terminal: str | None = None
        self._server = ThreadingHTTPServer(
            ("127.0.0.1", port), _make_handler(self),
        )
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def endpoint(self) -> str:
        port = self._server.server_address[1]
        return f"http://127.0.0.1:{port}/invoke"

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stop()


def _make_handler(agent: FakeHttpAgent):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_POST(self):
            length = int(self.headers.get("content-length", 0))
            raw = self.rfile.read(length) if length else b""
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                body = {}
            agent.received_headers.append(
                {k.lower(): v for k, v in self.headers.items()}
            )
            agent.received_bodies.append(body)

            if agent.behavior == "success":
                self._handle_success(body)
            elif agent.behavior == "success_title_case":
                self._handle_success(body, header_name="Content-Type")
            elif agent.behavior == "slow":
                import time
                time.sleep(10)
                self._handle_success(body)
            elif agent.behavior == "bad_content_type":
                self.send_response(200)
                self.send_header("content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"not json")
            elif agent.behavior == "missing_fields":
                response = json.dumps({"invocation_id": "inv", "final_state": {}})
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(response)))
                self.end_headers()
                self.wfile.write(response.encode())
            else:
                code = int(agent.behavior) if agent.behavior.isdigit() else 500
                self.send_response(code)
                self.send_header("content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": agent.behavior}).encode())

        def _handle_success(self, body: dict, header_name: str = "content-type"):
            traceparent = self.headers.get("traceparent", "")
            trace_id = _extract_trace_id(traceparent)
            run_id = self.headers.get("x-agentgate-run-id", "")
            case_id = self.headers.get("x-agentgate-case-id", "")
            output = {"message": "processed", "status": "approved"}
            final_state = {"approved": True, "status": "approved"}
            if agent.trace_export and agent.repository is not None:
                reports, status_before_terminal = _export_otlp(
                    agent.repository, trace_id, run_id, case_id,
                    body.get("turn_id"), body.get("invocation_id"),
                    output, final_state, agent.extra_span_count,
                    agent.export_batch_size, agent.include_duplicate,
                )
                agent.export_reports.extend(reports)
                agent.status_before_terminal = status_before_terminal
                agent.exported_trace_ids.append(trace_id)
            response = {
                "invocation_id": body.get("invocation_id", ""),
                "output": output,
                "final_state": final_state,
                "trace_id": trace_id,
            }
            payload = json.dumps(response).encode()
            self.send_response(200)
            self.send_header(header_name, "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return Handler


def _extract_trace_id(traceparent: str) -> str:
    parts = traceparent.split("-")
    if len(parts) >= 2 and len(parts[1]) == 32:
        return parts[1]
    return uuid4().hex


def _export_otlp(
    repository, trace_id: str, run_id: str, case_id: str,
    turn_id: str | None, invocation_id: str | None,
    output: dict[str, Any], final_state: dict[str, Any],
    extra_span_count: int = 0, batch_size: int = 100,
    include_duplicate: bool = False,
):
    """Export OpenInference-style OTLP spans to the repository."""
    from agentgate.trace.receivers.otlp_http import ingest_otlp_http_json
    ordinary_spans = [
                {
                    "traceId": trace_id,
                    "spanId": uuid4().hex[:16],
                    "name": "agent.invoke",
                    "attributes": [
                        {"key": "openinference.span.kind", "value": {"stringValue": "AGENT"}},
                        {"key": "llm.model_name", "value": {"stringValue": "demo-model"}},
                    ],
                },
                {
                    "traceId": trace_id,
                    "spanId": uuid4().hex[:16],
                    "parentSpanId": "",
                    "name": "tool.call",
                    "attributes": [
                        {"key": "openinference.span.kind", "value": {"stringValue": "TOOL"}},
                        {"key": "tool.name", "value": {"stringValue": "approve_loan"}},
                    ],
                },
                *[
                    {
                        "traceId": trace_id,
                        "spanId": uuid4().hex[:16],
                        "name": f"tool.batch.{index}",
                        "startTimeUnixNano": str(1_000 + index * 2),
                        "endTimeUnixNano": str(1_001 + index * 2),
                        "attributes": [{
                            "key": "openinference.span.kind",
                            "value": {"stringValue": "TOOL"},
                        }],
                    }
                    for index in range(extra_span_count)
                ],
    ]
    terminal_span = {
                    "traceId": trace_id,
                    "spanId": uuid4().hex[:16],
                    "name": "agent.complete",
                    "attributes": [
                        {
                            "key": "agentgate.span.kind",
                            "value": {"stringValue": "event"},
                        },
                        {
                            "key": "agentgate.turn.id",
                            "value": {"stringValue": turn_id},
                        },
                        {
                            "key": "agentgate.invocation.id",
                            "value": {"stringValue": invocation_id},
                        },
                        {
                            "key": "agentgate.trace.complete",
                            "value": {"stringValue": "true"},
                        },
                        {
                            "key": "agentgate.turn.complete",
                            "value": {"stringValue": "true"},
                        },
                        {
                            "key": "agentgate.final_output.json",
                            "value": {
                                "stringValue": json.dumps(output, ensure_ascii=False),
                            },
                        },
                        {
                            "key": "agentgate.final_state.json",
                            "value": {
                                "stringValue": json.dumps(
                                    final_state, ensure_ascii=False
                                ),
                            },
                        },
                    ],
                }

    def payload(spans):
        return {
            "resourceSpans": [{
                "resource": {"attributes": []},
                "scopeSpans": [{"spans": spans}],
            }]
        }

    reports = []
    reversed_spans = list(reversed(ordinary_spans))
    for offset in range(0, len(reversed_spans), batch_size):
        chunk = reversed_spans[offset:offset + batch_size]
        if include_duplicate and offset == 0:
            chunk = [*chunk, chunk[0]]
        reports.append(ingest_otlp_http_json(payload(chunk), repository))
    current = repository.get_trace(run_id, case_id)
    status_before_terminal = current.status.value if current is not None else None
    reports.append(ingest_otlp_http_json(payload([terminal_span]), repository))
    return reports, status_before_terminal
