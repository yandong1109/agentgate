"""Target execution adapter protocol, credential resolver, and error taxonomy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from agentgate.domain import TargetExecutionRequest, TargetExecutionResult


class TargetExecutionAdapter(Protocol):
    adapter_type: str
    adapter_version: str

    def execute(self, request: TargetExecutionRequest) -> TargetExecutionResult: ...


class CredentialResolver(Protocol):
    def resolve(self, credential_ref: str) -> ResolvedCredential: ...


@dataclass(frozen=True)
class ResolvedCredential:
    """Runtime-only credential holder; never serialized, persisted, or logged."""

    header_value: str | None


class EnvCredentialResolver:
    """POC credential resolver reading the env var named by ``credential_ref``."""

    def __init__(self) -> None:
        import os
        self._os = os

    def resolve(self, credential_ref: str) -> ResolvedCredential:
        if not credential_ref:
            return ResolvedCredential(header_value=None)
        value = self._os.environ.get(credential_ref)
        if value is None:
            raise TargetIntegrationError.unauthorized(
                f"credential env var not set: {credential_ref}"
            )
        return ResolvedCredential(header_value=value)


class TargetIntegrationError(Exception):
    """Base error for target integration failures."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")

    @staticmethod
    def target_not_found(message: str) -> TargetIntegrationError:
        return TargetIntegrationError("target_not_found", message)

    @staticmethod
    def unauthorized(message: str) -> TargetIntegrationError:
        return TargetIntegrationError("unauthorized", message)

    @staticmethod
    def invalid_configuration(message: str) -> TargetIntegrationError:
        return TargetIntegrationError("invalid_configuration", message)

    @staticmethod
    def rate_limited(message: str) -> TargetIntegrationError:
        return TargetIntegrationError("rate_limited", message)

    @staticmethod
    def timeout(message: str) -> TargetIntegrationError:
        return TargetIntegrationError("timeout", message)

    @staticmethod
    def unavailable(message: str) -> TargetIntegrationError:
        return TargetIntegrationError("unavailable", message)

    @staticmethod
    def rejected(message: str) -> TargetIntegrationError:
        return TargetIntegrationError("rejected", message)

    @staticmethod
    def protocol_error(message: str) -> TargetIntegrationError:
        return TargetIntegrationError("protocol_error", message)

    @staticmethod
    def version_not_found(message: str) -> TargetIntegrationError:
        return TargetIntegrationError("version_not_found", message)

    @staticmethod
    def trace_timeout(message: str) -> TargetIntegrationError:
        return TargetIntegrationError("trace_timeout", message)
