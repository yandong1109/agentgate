"""评测对象注册服务：注册、配置、版本化、连通性测试、注册表桥接。

安全红线：
- 只持久化 ``credential_ref``（环境变量名），密钥明文一律拒绝；
- 错误信息经 ``HttpTargetAdapter`` 的 ``_redact`` 脱敏后原样透出。
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Callable
from uuid import uuid4

from agentgate.domain import (
    TargetExecutionRequest,
    TargetRef,
    TargetSnapshot,
    TargetType,
    freeze_json,
)
from agentgate.run.targets.base import (
    EnvCredentialResolver,
    TargetIntegrationError,
)
from agentgate.run.targets.http import HttpTargetAdapter

from .domain import (
    DEFAULT_TIMEOUT_SECONDS,
    SUPPORTED_ADAPTER_TYPES,
    SUPPORTED_TARGET_TYPES,
    TARGET_STATUS_DELETED,
    TEST_CONNECTION_TIMEOUT_SECONDS,
    TargetEntity,
    TargetVersionEntity,
    compute_content_sha256,
    slugify,
    utcnow,
)
from .repository import TargetRepository

logger = logging.getLogger(__name__)

_ENDPOINT_RE = re.compile(r"^https?://\S+$")

# task 模块 AgentType 与适配器类型的映射（供 _get_target_info 数据源使用）
AGENT_TYPE_BY_ADAPTER = {
    "http": "REMOTE_AGENT",
    "python_fn": "AGENT_WORKFLOW",
}


class TargetError(Exception):
    """评测对象业务错误基类；status_code 由子类决定。"""

    status_code = 400


class TargetValidationError(TargetError):
    status_code = 400


class TargetNotFound(TargetError):
    status_code = 404


class TargetConflict(TargetError):
    status_code = 409


def _version_key(external_target_id: str, version: int) -> str:
    """注册表键，同时作为 TargetRef.external_version_id。"""
    return f"{external_target_id}-v{version}"


class TargetService:
    def __init__(
        self,
        repository: TargetRepository,
        has_run_references: Callable[[str], bool] | None = None,
    ) -> None:
        self.repository = repository
        self._has_run_references = has_run_references or (lambda external_id: False)

    # ── 校验 ─────────────────────────────────────────────────

    @staticmethod
    def _validate_endpoint(endpoint: str) -> None:
        if not endpoint or not _ENDPOINT_RE.match(endpoint):
            raise TargetValidationError(
                f"端点必须是 http(s) URL: {endpoint!r}"
            )

    @staticmethod
    def _validate_capabilities(capabilities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = []
        for item in capabilities or []:
            name = str(item.get("name", "")).strip()
            if not name:
                raise TargetValidationError("能力声明的 name 不能为空")
            normalized.append({
                "name": name,
                "kind": str(item.get("kind", "tool")).strip() or "tool",
                "description": str(item.get("description", "")),
            })
        return normalized

    def _allocate_external_id(self, display_name: str, requested: str | None) -> str:
        if requested:
            candidate = requested.strip()
        else:
            candidate = slugify(display_name)
        if not candidate:
            candidate = f"target-{uuid4().hex[:8]}"
        existing = self.repository.get_target_by_external_id(candidate)
        if existing is not None and existing.active:
            raise TargetConflict(f"评测对象已存在: {candidate}")
        return candidate

    # ── 注册（创建 + 自动发布 v1）─────────────────────────────

    def create_target(
        self,
        *,
        display_name: str,
        endpoint: str,
        target_type: str = "agent",
        adapter_type: str = "http",
        credential_ref: str | None = None,
        platform_id: str = "registered",
        external_target_id: str | None = None,
        description: str = "",
        capabilities: list[dict[str, Any]] | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[TargetEntity, TargetVersionEntity]:
        display_name = (display_name or "").strip()
        if not display_name:
            raise TargetValidationError("display_name 不能为空")
        if target_type not in SUPPORTED_TARGET_TYPES:
            raise TargetValidationError(
                f"target_type 必须是 {'/'.join(SUPPORTED_TARGET_TYPES)}: {target_type}"
            )
        if adapter_type not in SUPPORTED_ADAPTER_TYPES:
            raise TargetValidationError(
                f"adapter_type 必须是 {'/'.join(SUPPORTED_ADAPTER_TYPES)}: {adapter_type}"
            )
        self._validate_endpoint(endpoint)
        normalized_capabilities = self._validate_capabilities(capabilities or [])
        if credential_ref is not None:
            credential_ref = credential_ref.strip() or None

        external_id = self._allocate_external_id(display_name, external_target_id)
        target = TargetEntity(
            id=str(uuid4()),
            display_name=display_name,
            target_type=target_type,
            adapter_type=adapter_type,
            external_target_id=external_id,
            platform_id=platform_id or "registered",
            description=description or "",
            capabilities=normalized_capabilities,
        )
        self.repository.create_target(target)
        version = self.publish_version(
            target.id,
            endpoint=endpoint,
            credential_ref=credential_ref,
            capabilities=normalized_capabilities,
            timeout_seconds=timeout_seconds,
        )
        logger.info("评测对象已注册: %s (v1, endpoint=%s)", external_id, endpoint)
        return target, version

    # ── 版本发布（不可变快照）────────────────────────────────

    def publish_version(
        self,
        target_id: str,
        *,
        endpoint: str | None = None,
        credential_ref: str | None = None,
        capabilities: list[dict[str, Any]] | None = None,
        timeout_seconds: float | None = None,
    ) -> TargetVersionEntity:
        """发布新版本；未指定的字段继承上一版本（同配置重发得到相同内容哈希）。"""
        target = self._get_active_target(target_id)
        previous = self.repository.get_latest_version(target.id)
        if previous is None:
            effective_endpoint = endpoint
            if effective_endpoint is None:
                raise TargetValidationError("首个版本必须提供 endpoint")
            effective_credential = credential_ref
            effective_capabilities = (
                capabilities if capabilities is not None
                else list(target.capabilities)
            )
            effective_timeout = timeout_seconds or DEFAULT_TIMEOUT_SECONDS
        else:
            effective_endpoint = endpoint if endpoint is not None else previous.endpoint
            effective_credential = (
                credential_ref if credential_ref is not None else previous.credential_ref
            )
            effective_capabilities = (
                capabilities if capabilities is not None else list(previous.capabilities)
            )
            effective_timeout = (
                timeout_seconds if timeout_seconds is not None
                else previous.timeout_seconds
            )
        self._validate_endpoint(effective_endpoint)
        effective_capabilities = self._validate_capabilities(effective_capabilities)
        if effective_timeout is None or effective_timeout <= 0:
            raise TargetValidationError("timeout_seconds 必须大于 0")

        invocation_config = {"timeout_seconds": float(effective_timeout)}
        content_sha256 = compute_content_sha256(
            effective_endpoint, effective_credential,
            invocation_config, effective_capabilities,
        )
        version = TargetVersionEntity(
            id=str(uuid4()),
            target_id=target.id,
            version=(previous.version + 1) if previous else 1,
            endpoint=effective_endpoint,
            credential_ref=effective_credential,
            invocation_config=invocation_config,
            capabilities=effective_capabilities,
            content_sha256=content_sha256,
            is_latest=True,
            published_at=utcnow(),
        )
        self.repository.insert_version(version)
        logger.info(
            "评测对象版本已发布: %s (sha256=%s)",
            _version_key(target.external_target_id, version.version),
            content_sha256[:12],
        )
        return version

    # ── 读取模型 ─────────────────────────────────────────────

    def _get_active_target(self, target_id: str) -> TargetEntity:
        target = self.repository.get_target(target_id)
        if target is None:
            raise TargetNotFound(f"评测对象不存在: {target_id}")
        if target.status == TARGET_STATUS_DELETED:
            raise TargetNotFound(f"评测对象已删除: {target_id}")
        return target

    def list_targets(self, target_type: str | None = None) -> list[dict[str, Any]]:
        summaries = []
        for target in self.repository.list_targets(active_only=True):
            if target_type and target.target_type != target_type:
                continue
            summaries.append(self._target_summary(target))
        return summaries

    def _target_summary(self, target: TargetEntity) -> dict[str, Any]:
        versions = self.repository.list_versions(target.id)
        latest = next((item for item in versions if item.is_latest), None)
        return {
            **target.to_dict(),
            "version_count": len(versions),
            "latest_version": latest.to_dict() if latest else None,
        }

    def get_target(self, target_id: str) -> dict[str, Any]:
        target = self._get_active_target(target_id)
        versions = self.repository.list_versions(target.id)
        return {
            **target.to_dict(),
            "versions": [item.to_dict() for item in versions],
        }

    def update_target(
        self,
        target_id: str,
        *,
        display_name: str | None = None,
        description: str | None = None,
        capabilities: list[dict[str, Any]] | None = None,
    ) -> TargetEntity:
        """仅更新可变元数据；端点/认证等执行配置只能通过发布新版本变更。"""
        target = self._get_active_target(target_id)
        if display_name is not None:
            display_name = display_name.strip()
            if not display_name:
                raise TargetValidationError("display_name 不能为空")
            target.display_name = display_name
        if description is not None:
            target.description = description
        if capabilities is not None:
            target.capabilities = self._validate_capabilities(capabilities)
        self.repository.update_target(target)
        return target

    def delete_target(self, target_id: str) -> dict[str, Any]:
        """软删除；被运行记录引用的评测对象拒绝删除（保住历史 run 的可解释性）。"""
        target = self._get_active_target(target_id)
        if self._has_run_references(target.external_target_id):
            raise TargetConflict(
                f"评测对象 {target.external_target_id} 已被运行记录引用，无法删除"
            )
        target.status = TARGET_STATUS_DELETED
        # 释放 external_target_id，允许同名对象重新注册（保留行以备审计）
        target.external_target_id = f"{target.external_target_id}~deleted-{uuid4().hex[:8]}"
        self.repository.update_target(target)
        logger.info("评测对象已软删除: %s", target_id)
        return {"deleted": True, "id": target_id}

    # ── 连通性测试 ───────────────────────────────────────────

    def _probe(
        self, endpoint: str, credential_ref: str | None, timeout_seconds: float,
    ) -> dict[str, Any]:
        snapshot = TargetSnapshot(
            ref=TargetRef(
                platform_id="agentgate",
                target_type=TargetType.AGENT,
                external_target_id="test-connection",
                external_version_id="probe",
            ),
            display_name="test-connection",
            adapter_type="http",
            adapter_version="1",
            invocation_config=freeze_json({
                "endpoint": endpoint,
                "timeout_seconds": timeout_seconds,
            }),
            credential_ref=credential_ref,
        )
        adapter = HttpTargetAdapter(endpoint, EnvCredentialResolver())
        request = TargetExecutionRequest(
            invocation_id=f"conn-{uuid4()}",
            idempotency_key=f"conn-{uuid4()}",
            run_id="test-connection",
            case_id="test-connection",
            target=snapshot,
            input=freeze_json({"ping": "agentgate-test-connection"}),
            state=freeze_json({}),
            timeout_seconds=timeout_seconds,
            traceparent="00-" + "0" * 32 + "-" + "0" * 16 + "-01",
        )
        started = time.perf_counter()
        try:
            result = adapter.execute(request)
        except TargetIntegrationError as exc:
            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            return {
                "ok": False,
                "error_code": exc.code,
                "message": str(exc),
                "latency_ms": latency_ms,
            }
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        return {"ok": True, "latency_ms": latency_ms, "trace_id": result.trace_id}

    def test_connection(
        self,
        *,
        endpoint: str | None = None,
        credential_ref: str | None = None,
        timeout_seconds: float = TEST_CONNECTION_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        """向导中的临时探测：无需先注册。"""
        self._validate_endpoint(endpoint or "")
        return self._probe(endpoint, credential_ref, timeout_seconds)

    def test_target_connection(
        self, target_id: str, version: int | None = None,
    ) -> dict[str, Any]:
        """对已注册评测对象（默认最新版本）做连通性测试。"""
        target = self._get_active_target(target_id)
        if version is not None:
            ver = self.repository.get_version(target.id, version)
            if ver is None:
                raise TargetNotFound(f"版本不存在: v{version}")
        else:
            ver = self.repository.get_latest_version(target.id)
            if ver is None:
                raise TargetValidationError("评测对象尚未发布任何版本")
        return self._probe(
            ver.endpoint, ver.credential_ref,
            min(ver.timeout_seconds, TEST_CONNECTION_TIMEOUT_SECONDS),
        )

    # ── 控制平面桥接 ─────────────────────────────────────────

    def build_registrations(self) -> list[Any]:
        """把已注册评测对象的全部已发布版本转成控制平面 TargetRegistration。

        函数内导入避免模块级循环依赖（control_plane 不反向依赖本模块）。
        """
        from agentgate.control_plane.service import TargetRegistration

        registrations = []
        for target in self.repository.list_targets(active_only=True):
            if target.adapter_type != "http":
                continue
            for ver in self.repository.list_versions(target.id):
                key = _version_key(target.external_target_id, ver.version)
                registrations.append(TargetRegistration(
                    target_id=key,
                    label=f"{target.display_name} · v{ver.version}",
                    adapter_type="http",
                    target_ref=TargetRef(
                        platform_id=target.platform_id,
                        target_type=TargetType(target.target_type),
                        external_target_id=target.external_target_id,
                        external_version_id=key,
                    ),
                    invocation_config={
                        "endpoint": ver.endpoint,
                        "timeout_seconds": ver.timeout_seconds,
                    },
                    credential_ref=ver.credential_ref,
                    is_latest=ver.is_latest,
                ))
        return registrations

    def get_target_info(self, key: str) -> dict[str, Any]:
        """task 模块 ``_get_target_info`` 的数据源。

        ``key`` 既可以是版本键（``<external_id>-v<n>``）也可以是对象 ID；
        解析失败时返回与旧行为一致的回退结构。
        """
        target = self.repository.get_target_by_external_id(key)
        version = None
        if target is not None:
            version = self.repository.get_latest_version(target.id)
        else:
            match = re.match(r"^(?P<ext>.+)-v(?P<num>\d+)$", key)
            if match:
                target = self.repository.get_target_by_external_id(match.group("ext"))
                if target is not None:
                    version = self.repository.get_version(
                        target.id, int(match.group("num"))
                    )
        if target is None or version is None:
            return {
                "agent_name": key,
                "agent_type": "REMOTE_AGENT",
                "config": {},
                "status": "ACTIVE",
            }
        return {
            "agent_name": target.display_name,
            "agent_type": AGENT_TYPE_BY_ADAPTER.get(
                target.adapter_type, "REMOTE_AGENT"
            ),
            "config": {
                "endpoint": version.endpoint,
                "credential_ref": version.credential_ref,
            },
            "status": "ACTIVE",
        }
