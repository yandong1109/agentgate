"""HTTP target adapter calling an external Agent HTTP API."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from agentgate.domain import (
    TargetExecutionRequest,
    TargetExecutionResult,
    freeze_json,
)

from .base import (
    CredentialResolver,
    ResolvedCredential,
    TargetIntegrationError,
)

LOGGER = logging.getLogger(__name__)

_SECRET_RE = re.compile(
    r"(?i)"
    r"(authorization|token|secret|password|api[_-]?key)\s*[=:]\s*[^,;\n\r]+"
    r"|"
    r"bearer\s+\S+"
)


def _redact(text: str) -> str:
    def _replace(match: re.Match) -> str:
        if match.group(1):
            return f"{match.group(1)}=[redacted]"
        return "[redacted]"

    return _SECRET_RE.sub(_replace, text)


class HttpTargetAdapter:
    """Adapter that POSTs to an external Agent HTTP endpoint."""

    adapter_type = "http"
    adapter_version = "1"

    def __init__(
        self, endpoint: str, credential_resolver: CredentialResolver | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.credential_resolver = credential_resolver

    def execute(self, request: TargetExecutionRequest) -> TargetExecutionResult:
        credential = _resolve_credential(self.credential_resolver, request)
        input_payload, envelope_turn_id = _unwrap_single_turn(request.input.to_dict())
        turn_id = request.turn_id if request.turn_id is not None else envelope_turn_id
        body = _build_body(request, input_payload, turn_id)
        headers = _build_headers(request, credential, turn_id)
        try:
            response = _post(self.endpoint, body, headers, request.timeout_seconds)
        except HTTPError as exc:
            raise _map_http_error(exc) from exc
        except (TimeoutError, URLError) as exc:
            raise TargetIntegrationError.timeout(
                f"HTTP request timed out: {_redact(str(exc))}"
            ) from exc
        except Exception as exc:
            raise TargetIntegrationError.unavailable(
                f"unexpected HTTP error: {_redact(str(exc))}"
            ) from exc
        _validate_content_type(response)
        payload = _parse_json(response)
        _validate_response_shape(payload)
        trace_id = payload.get("trace_id") or _extract_trace_id(request.traceparent)
        return TargetExecutionResult(
            invocation_id=request.invocation_id,
            external_execution_id=payload.get("external_execution_id"),
            output=freeze_json(payload["output"]),
            final_state=freeze_json(payload["final_state"]),
            inline_trace=None,
            trace_id=trace_id,
            completed_at=datetime.now(UTC),
        )


def _resolve_credential(
    resolver: CredentialResolver | None, request: TargetExecutionRequest
) -> ResolvedCredential | None:
    if resolver is None or not request.target.credential_ref:
        return None
    return resolver.resolve(request.target.credential_ref)


def _unwrap_single_turn(
    input_data: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    """Flatten the RunEngine's single-turn ``{"turns": [...]}`` envelope.

    The documented Invoke contract (docs/run/demo-agent-plan.md) puts the
    turn input inline as a flat ``input`` object with ``turn_id`` at the top
    level. The engine serializes a whole Case into a turns envelope for the
    python_fn adapter to reconstruct; the HTTP wire format must not leak that
    internal shape. Single-turn envelopes are unwrapped to the flat contract,
    multi-turn envelopes pass through unchanged.
    """
    turns = input_data.get("turns")
    if (
        isinstance(turns, list)
        and len(turns) == 1
        and isinstance(turns[0], dict)
        and "turn_id" in turns[0]
        and isinstance(turns[0].get("input"), dict)
    ):
        turn = turns[0]
        return turn["input"], turn.get("turn_id")
    return input_data, None


def _build_body(
    request: TargetExecutionRequest,
    input_payload: dict[str, Any],
    turn_id: str | None,
) -> bytes:
    ref = request.target.ref
    return json.dumps({
        "invocation_id": request.invocation_id,
        "idempotency_key": request.idempotency_key,
        "target": {
            "type": ref.target_type.value,
            "id": ref.external_target_id,
            "version_id": ref.external_version_id,
        },
        "run_id": request.run_id,
        "case_id": request.case_id,
        "turn_id": turn_id,
        "input": input_payload,
        "state": request.state.to_dict(),
    }, ensure_ascii=False).encode("utf-8")


def _build_headers(
    request: TargetExecutionRequest,
    credential: ResolvedCredential | None,
    turn_id: str | None,
) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "traceparent": request.traceparent,
        "Idempotency-Key": request.idempotency_key,
        "X-AgentGate-Run-Id": request.run_id,
        "X-AgentGate-Case-Id": request.case_id,
    }
    if turn_id is not None:
        headers["X-AgentGate-Turn-Id"] = turn_id
    if request.baggage:
        headers["baggage"] = request.baggage
    if credential and credential.header_value:
        headers["Authorization"] = credential.header_value
    return headers


def _post(
    endpoint: str, body: bytes, headers: dict[str, str], timeout: float
) -> tuple[int, dict[str, str], bytes]:
    req = Request(endpoint, data=body, headers=headers, method="POST")
    with urlopen(req, timeout=timeout) as resp:
        # Normalize to lowercase: HTTP headers are case-insensitive, but a plain
        # dict built from the raw message preserves the sender's casing.
        response_headers = {
            key.lower(): value for key, value in resp.headers.items()
        }
        return resp.status, response_headers, resp.read()


def _map_http_error(exc: HTTPError) -> TargetIntegrationError:
    code = exc.code
    detail = _redact(str(exc))
    if code == 401:
        return TargetIntegrationError.unauthorized(detail)
    if code == 404:
        return TargetIntegrationError.target_not_found(detail)
    if code == 429:
        return TargetIntegrationError.rate_limited(detail)
    if 500 <= code < 600:
        return TargetIntegrationError.unavailable(detail)
    return TargetIntegrationError.protocol_error(f"HTTP {code}: {detail}")


def _validate_content_type(response: tuple[int, dict[str, str], bytes]) -> None:
    _, headers, _ = response
    content_type = headers.get("content-type", "")
    if "json" not in content_type.lower():
        raise TargetIntegrationError.protocol_error(
            f"expected JSON content-type, got {content_type!r}"
        )


def _parse_json(response: tuple[int, dict[str, str], bytes]) -> dict[str, Any]:
    _, _, body = response
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, TypeError) as exc:
        raise TargetIntegrationError.protocol_error(
            f"invalid JSON response: {_redact(str(exc))}"
        ) from exc
    if not isinstance(data, dict):
        raise TargetIntegrationError.protocol_error("response is not a JSON object")
    return data


def _validate_response_shape(payload: dict[str, Any]) -> None:
    missing = [key for key in ("output", "final_state") if key not in payload]
    if missing:
        raise TargetIntegrationError.protocol_error(
            f"response missing required fields: {', '.join(missing)}"
        )


def _extract_trace_id(traceparent: str) -> str | None:
    parts = traceparent.split("-")
    if len(parts) >= 2 and len(parts[1]) == 32:
        return parts[1]
    return None
