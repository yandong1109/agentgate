"""External target identity and execution contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field, model_validator

from .base import DomainModel, FrozenJsonObject, FrozenJsonValue, content_sha256
from .trace import Trace


def utcnow() -> datetime:
    return datetime.now(UTC)


class TargetType(StrEnum):
    AGENT = "agent"
    SKILL = "skill"


class TargetRef(DomainModel):
    platform_id: str
    target_type: TargetType
    external_target_id: str
    external_version_id: str

    @model_validator(mode="after")
    def validate_non_empty(self) -> TargetRef:
        for field in ("platform_id", "external_target_id", "external_version_id"):
            if not getattr(self, field):
                raise ValueError(f"{field} must be non-empty")
        return self


class TargetSnapshot(DomainModel):
    ref: TargetRef
    display_name: str
    adapter_type: str
    adapter_version: str
    descriptor_sha256: str = ""
    invocation_config: FrozenJsonObject = Field(default_factory=FrozenJsonObject)
    credential_ref: str | None = None
    captured_at: datetime = Field(default_factory=utcnow)
    content_sha256: str = ""

    @model_validator(mode="after")
    def set_or_verify_hash(self) -> TargetSnapshot:
        payload = self.model_dump(mode="json", exclude={"content_sha256"})
        expected = content_sha256(payload)
        if self.content_sha256 and self.content_sha256 != expected:
            raise ValueError("TargetSnapshot content hash mismatch")
        if not self.content_sha256:
            object.__setattr__(self, "content_sha256", expected)
        return self


class TargetExecutionRequest(DomainModel):
    invocation_id: str
    idempotency_key: str
    run_id: str
    case_id: str
    turn_id: str | None = None
    target: TargetSnapshot
    input: FrozenJsonObject = Field(default_factory=FrozenJsonObject)
    state: FrozenJsonObject = Field(default_factory=FrozenJsonObject)
    timeout_seconds: float = 30.0
    traceparent: str
    baggage: str | None = None


class TargetExecutionResult(DomainModel):
    invocation_id: str
    external_execution_id: str | None = None
    output: FrozenJsonValue = None
    final_state: FrozenJsonObject = Field(default_factory=FrozenJsonObject)
    inline_trace: Trace | None = None
    trace_id: str | None = None
    completed_at: datetime = Field(default_factory=utcnow)
