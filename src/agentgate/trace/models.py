"""Transport-independent runtime models for trace ingestion."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import NAMESPACE_URL, uuid4, uuid5

from pydantic import Field, field_serializer, model_validator

from agentgate.domain import DomainModel, FrozenJsonObject, SpanKind, content_sha256
from agentgate.domain.base import freeze_json, thaw_json

SignalKind = Literal["trace_complete", "turn_complete", "final_output", "final_state"]
ConflictKind = Literal["span_content", "semantic_signal", "correlation", "topology"]


class OtlpIngestionLimits(DomainModel):
    max_request_bytes: int = Field(default=4 * 1024 * 1024, ge=1)
    max_decompressed_bytes: int = Field(default=8 * 1024 * 1024, ge=1)
    max_resources: int = Field(default=128, ge=1)
    max_scopes_per_resource: int = Field(default=128, ge=1)
    max_spans: int = Field(default=10_000, ge=1)
    max_attributes: int = Field(default=128, ge=1)
    max_events: int = Field(default=128, ge=0)
    max_links: int = Field(default=128, ge=0)
    max_key_length: int = Field(default=256, ge=1)
    max_string_length: int = Field(default=16_384, ge=1)
    max_anyvalue_depth: int = Field(default=8, ge=1)
    max_normalized_bytes: int = Field(default=16 * 1024 * 1024, ge=1)


class NormalizedSpan(DomainModel):
    run_id: str
    case_id: str
    source_trace_id: str
    source_span_id: str
    parent_span_id: str | None = None
    turn_id: str | None = None
    invocation_id: str | None = None
    invocation_attempt: int = Field(default=0, ge=0)
    name: str
    kind: SpanKind = SpanKind.EVENT
    otel_kind: int | None = Field(default=None, ge=0)
    scope_name: str | None = None
    scope_version: str | None = None
    start_time_unix_nano: int | None = Field(default=None, ge=0)
    end_time_unix_nano: int | None = Field(default=None, ge=0)
    attributes: FrozenJsonObject = Field(default_factory=FrozenJsonObject)
    events: tuple[FrozenJsonObject, ...] = ()
    links: tuple[FrozenJsonObject, ...] = ()
    dropped_attributes_count: int = Field(default=0, ge=0)
    dropped_events_count: int = Field(default=0, ge=0)
    dropped_links_count: int = Field(default=0, ge=0)
    status: str = "unset"
    status_message: str = ""


class NormalizedSignal(DomainModel):
    id: str = ""
    run_id: str
    case_id: str
    source_trace_id: str
    source_span_id: str
    turn_id: str | None = None
    invocation_id: str | None = None
    kind: SignalKind
    value: Any = None
    precedence: int = Field(default=1, ge=0)
    content_sha256: str = ""

    @model_validator(mode="before")
    @classmethod
    def freeze_value(cls, value: Any) -> Any:
        if isinstance(value, dict) and "value" in value:
            value = dict(value)
            value["value"] = freeze_json(value["value"])
        return value

    @field_serializer("value")
    def serialize_value(self, value: Any) -> Any:
        return thaw_json(value)

    @model_validator(mode="after")
    def set_identity_and_hash(self) -> "NormalizedSignal":
        identity = (
            f"agentgate-signal-v1:{self.run_id}:{self.case_id}:"
            f"{self.source_trace_id}:{self.source_span_id}:{self.kind}"
        )
        if not self.id:
            object.__setattr__(self, "id", str(uuid5(NAMESPACE_URL, identity)))
        payload = self.model_dump(mode="json", exclude={"id", "content_sha256"})
        expected = content_sha256(payload)
        if self.content_sha256 and self.content_sha256 != expected:
            raise ValueError("NormalizedSignal content hash mismatch")
        if not self.content_sha256:
            object.__setattr__(self, "content_sha256", expected)
        return self


class TraceConflict(DomainModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    kind: ConflictKind
    run_id: str | None = None
    case_id: str | None = None
    source_trace_id: str | None = None
    source_span_id: str | None = None
    original_sha256: str = ""
    conflicting_sha256: str = ""
    summary: str
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TraceBatch(DomainModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    source: str = "otlp-http-json"
    content_sha256: str
    spans: tuple[NormalizedSpan, ...] = ()
    signals: tuple[NormalizedSignal, ...] = ()
    conflicts: tuple[TraceConflict, ...] = ()
    errors: tuple[str, ...] = ()
    rejected_spans: int = Field(default=0, ge=0)
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IngestionReport(DomainModel):
    accepted_spans: int = Field(default=0, ge=0)
    duplicate_spans: int = Field(default=0, ge=0)
    rejected_spans: int = Field(default=0, ge=0)
    conflicted_spans: int = Field(default=0, ge=0)
    accepted_signals: int = Field(default=0, ge=0)
    duplicate_signals: int = Field(default=0, ge=0)
    conflicted_signals: int = Field(default=0, ge=0)
    affected_traces: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
