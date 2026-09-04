"""Vendor-neutral, deterministic canonical trace models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import NAMESPACE_URL, uuid4, uuid5

from pydantic import Field, field_serializer, model_validator

from .base import DomainModel, FrozenJsonObject, content_sha256, freeze_json, thaw_json

TRACE_NAMESPACE = "agentgate-trace-v1"


def utcnow() -> datetime:
    return datetime.now(UTC)


class SpanKind(StrEnum):
    ROUTING = "routing"
    AGENT = "agent"
    TOOL = "tool"
    STATE = "state"
    EVENT = "event"


class TraceStatus(StrEnum):
    COLLECTING = "collecting"
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    CONFLICTED = "conflicted"


class TraceCompletenessPolicy(DomainModel):
    expected_turn_count: int | None = Field(default=None, ge=1)
    require_execution_result: bool = False
    require_terminal_signal: bool = True
    require_final_output: bool = False
    require_final_state: bool = False
    quiet_period_ms: int = Field(default=0, ge=0)
    deadline_seconds: int = Field(default=30, ge=1)
    late_arrival_policy: Literal["new_revision", "reject"] = "new_revision"


def canonical_trace_id(run_id: str, case_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{TRACE_NAMESPACE}:{run_id}:{case_id}"))


def canonical_span_id(
    run_id: str, case_id: str, source_trace_id: str, source_span_id: str
) -> str:
    return str(uuid5(
        NAMESPACE_URL,
        f"{TRACE_NAMESPACE}:{run_id}:{case_id}:{source_trace_id}:{source_span_id}",
    ))


class TraceSpan(DomainModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str
    parent_id: str | None = None
    source_trace_id: str | None = None
    source_span_id: str | None = None
    run_id: str | None = None
    case_id: str | None = None
    turn_id: str | None = None
    invocation_id: str | None = None
    invocation_attempt: int = Field(default=0, ge=0)
    otel_kind: int | None = Field(default=None, ge=0)
    scope_name: str | None = None
    scope_version: str | None = None
    name: str
    kind: SpanKind
    sequence: int = Field(ge=0)
    started_at: datetime = Field(default_factory=utcnow)
    ended_at: datetime = Field(default_factory=utcnow)
    start_time_unix_nano: int | None = Field(default=None, ge=0)
    end_time_unix_nano: int | None = Field(default=None, ge=0)
    attributes: FrozenJsonObject = Field(default_factory=FrozenJsonObject)
    events: tuple[FrozenJsonObject, ...] = ()
    links: tuple[FrozenJsonObject, ...] = ()
    dropped_attributes_count: int = Field(default=0, ge=0)
    dropped_events_count: int = Field(default=0, ge=0)
    dropped_links_count: int = Field(default=0, ge=0)
    status: str = "ok"
    status_message: str = ""
    content_sha256: str = ""

    @model_validator(mode="after")
    def set_or_verify_hash(self) -> "TraceSpan":
        if (
            self.start_time_unix_nano is not None
            and self.end_time_unix_nano is not None
            and self.end_time_unix_nano < self.start_time_unix_nano
        ):
            raise ValueError("span end time cannot precede start time")
        payload = self.model_dump(
            mode="json", exclude={"id", "sequence", "content_sha256"}
        )
        expected = content_sha256(payload)
        if self.content_sha256 and self.content_sha256 != expected:
            raise ValueError("TraceSpan content hash mismatch")
        if not self.content_sha256:
            object.__setattr__(self, "content_sha256", expected)
        return self


class TraceTurn(DomainModel):
    turn_id: str
    turn_index: int = Field(default=0, ge=0)
    input: FrozenJsonObject
    output_present: bool = False
    output: Any = None
    state_present: bool = False
    state: FrozenJsonObject = Field(default_factory=FrozenJsonObject)
    invocation_ids: tuple[str, ...] = ()
    completed: bool = False

    @model_validator(mode="before")
    @classmethod
    def preserve_legacy_presence(cls, value: Any) -> Any:
        if isinstance(value, dict):
            value = dict(value)
            if "output" in value and "output_present" not in value:
                value["output_present"] = True
            if "state" in value and "state_present" not in value:
                value["state_present"] = True
            if "output" in value:
                value["output"] = freeze_json(value["output"])
        return value

    @field_serializer("output")
    def serialize_output(self, value: Any) -> Any:
        return thaw_json(value)


class Trace(DomainModel):
    id: str = ""
    run_id: str
    case_id: str
    status: TraceStatus = TraceStatus.COMPLETE
    revision: int = Field(default=1, ge=1)
    spans: tuple[TraceSpan, ...]
    turns: tuple[TraceTurn, ...] = ()
    final_output_present: bool = False
    final_output: Any = None
    final_state_present: bool = False
    final_state: FrozenJsonObject = Field(default_factory=FrozenJsonObject)
    source_trace_ids: tuple[str, ...] = ()
    conflict_count: int = Field(default=0, ge=0)
    completed_at: datetime | None = None
    content_sha256: str = ""

    @model_validator(mode="before")
    @classmethod
    def preserve_legacy_presence(cls, value: Any) -> Any:
        if isinstance(value, dict):
            value = dict(value)
            if "final_output" in value and "final_output_present" not in value:
                value["final_output_present"] = True
            if "final_state" in value and "final_state_present" not in value:
                value["final_state_present"] = True
            if "final_output" in value:
                value["final_output"] = freeze_json(value["final_output"])
        return value

    @field_serializer("final_output")
    def serialize_final_output(self, value: Any) -> Any:
        return thaw_json(value)

    @model_validator(mode="after")
    def set_identity_and_hash(self) -> "Trace":
        if not self.id:
            object.__setattr__(self, "id", canonical_trace_id(self.run_id, self.case_id))
        if not self.source_trace_ids:
            source_ids = sorted({
                span.source_trace_id or span.trace_id for span in self.spans
            })
            object.__setattr__(self, "source_trace_ids", tuple(source_ids))
        payload = self.model_dump(
            mode="json", exclude={"content_sha256", "revision"}
        )
        expected_hash = content_sha256(payload)
        if self.content_sha256 and self.content_sha256 != expected_hash:
            raise ValueError("Trace content hash mismatch")
        if not self.content_sha256:
            object.__setattr__(self, "content_sha256", expected_hash)
        return self

    def completion_sequence(self) -> int:
        return max((span.sequence for span in self.spans), default=-1) + 1

    def for_turn(self, turn_id: str) -> Trace:
        record = next((item for item in self.turns if item.turn_id == turn_id), None)
        if record is None:
            if len(self.turns) <= 1:
                return self
            raise ValueError(f"trace has no outcome for turn {turn_id}")
        spans = tuple(
            span for span in self.spans
            if span.turn_id == turn_id or span.attributes.get("turn_id") == turn_id
        )
        return self.model_copy(update={
            "spans": spans,
            "final_output_present": record.output_present,
            "final_output": record.output,
            "final_state_present": record.state_present,
            "final_state": record.state,
            "content_sha256": "",
        })
