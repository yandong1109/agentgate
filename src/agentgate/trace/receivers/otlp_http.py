"""OTLP/HTTP JSON receiver boundary."""

from __future__ import annotations

import base64
import gzip
import io
import logging
from typing import Any

from agentgate.trace.models import IngestionReport, OtlpIngestionLimits
from agentgate.trace.normalizer import normalize_otlp_json
from agentgate.trace.service import TraceIngestionService, TraceRepository

LOGGER = logging.getLogger(__name__)


def ingest_otlp_http_json(
    payload: dict[str, Any], repository: TraceRepository,
    limits: OtlpIngestionLimits | None = None,
) -> IngestionReport:
    def resolver(trace_id: str):
        getter = getattr(repository, "get_pending_trace", None)
        pending = getter(trace_id) if getter is not None else None
        if pending is None:
            return None
        return pending.run_id, pending.case_id, pending.invocation_id

    batch = normalize_otlp_json(
        payload, limits, correlation_resolver=resolver
    )
    return TraceIngestionService(repository).ingest(batch)


def decode_otlp_http_protobuf(body: bytes) -> dict[str, Any]:
    try:
        from google.protobuf.json_format import MessageToDict
        from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
            ExportTraceServiceRequest,
        )
    except ImportError as exc:  # pragma: no cover - packaging guarantees dependency
        raise RuntimeError("OTLP protobuf support is not installed") from exc
    from google.protobuf.message import DecodeError

    request = ExportTraceServiceRequest()
    try:
        request.ParseFromString(body)
    except DecodeError as exc:
        raise ValueError("invalid OTLP protobuf payload") from exc
    payload = MessageToDict(
        request, preserving_proto_field_name=False, use_integers_for_enums=True
    )

    # Protobuf JSON represents bytes as base64, while OTLP/HTTP JSON specifies
    # trace/span identifiers as hexadecimal strings.
    for resource in payload.get("resourceSpans", []):
        for scope in resource.get("scopeSpans", []):
            for span in scope.get("spans", []):
                for key in ("traceId", "spanId", "parentSpanId"):
                    if span.get(key):
                        span[key] = base64.b64decode(span[key]).hex()
                for link in span.get("links", []):
                    for key in ("traceId", "spanId"):
                        if link.get(key):
                            link[key] = base64.b64decode(link[key]).hex()
    return payload


def ingest_otlp_http_protobuf(
    body: bytes, repository: TraceRepository,
    limits: OtlpIngestionLimits | None = None,
) -> IngestionReport:
    return ingest_otlp_http_json(decode_otlp_http_protobuf(body), repository, limits)


def decode_content_encoding(
    body: bytes, content_encoding: str, limits: OtlpIngestionLimits
) -> bytes:
    encoding = content_encoding.strip().lower()
    if encoding in ("", "identity"):
        return body
    if encoding != "gzip":
        raise ValueError(f"unsupported Content-Encoding: {content_encoding}")
    with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:
        decoded = stream.read(limits.max_decompressed_bytes + 1)
    if len(decoded) > limits.max_decompressed_bytes:
        raise ValueError("decompressed OTLP request is too large")
    return decoded


def encode_otlp_http_protobuf_response(report: IngestionReport) -> bytes:
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
        ExportTracePartialSuccess, ExportTraceServiceResponse,
    )
    response = ExportTraceServiceResponse()
    rejected = report.rejected_spans + report.conflicted_spans
    if rejected:
        response.partial_success.CopyFrom(ExportTracePartialSuccess(
            rejected_spans=rejected,
            error_message="; ".join(report.errors[:3]),
        ))
    return response.SerializeToString()
