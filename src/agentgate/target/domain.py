"""评测对象注册域实体与内容哈希。

安全红线：本模块及其持久化层只承载 ``credential_ref``（环境变量名等不透明引用），
任何密钥明文不得进入实体、数据库或日志。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

TARGET_STATUS_ACTIVE = "ACTIVE"
TARGET_STATUS_DELETED = "DELETED"

SUPPORTED_TARGET_TYPES = ("agent", "skill")
SUPPORTED_ADAPTER_TYPES = ("http",)

DEFAULT_TIMEOUT_SECONDS = 30.0
TEST_CONNECTION_TIMEOUT_SECONDS = 10.0

_SLUG_STRIP_RE = re.compile(r"[^a-z0-9._-]+")


def utcnow() -> datetime:
    return datetime.now(UTC)


def slugify(display_name: str) -> str:
    """从展示名派生 URL 友好的外部对象 ID；无法派生时返回空串由调用方兜底。"""
    slug = _SLUG_STRIP_RE.sub("-", display_name.strip().lower()).strip("-")
    return slug


def compute_content_sha256(
    endpoint: str,
    credential_ref: str | None,
    invocation_config: dict[str, Any],
    capabilities: list[dict[str, Any]],
) -> str:
    """版本内容哈希：同一配置重复发布得到相同哈希；配置变化则哈希变化。"""
    payload = {
        "endpoint": endpoint,
        "credential_ref": credential_ref,
        "invocation_config": invocation_config,
        "capabilities": capabilities,
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class TargetEntity:
    """评测对象注册实体（可变元数据；执行配置固化在版本中）。"""

    id: str
    display_name: str
    target_type: str
    adapter_type: str
    external_target_id: str
    platform_id: str = "registered"
    description: str = ""
    capabilities: list[dict[str, Any]] = field(default_factory=list)
    status: str = TARGET_STATUS_ACTIVE
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    @property
    def active(self) -> bool:
        return self.status == TARGET_STATUS_ACTIVE

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "target_type": self.target_type,
            "adapter_type": self.adapter_type,
            "external_target_id": self.external_target_id,
            "platform_id": self.platform_id,
            "description": self.description,
            "capabilities": [dict(item) for item in self.capabilities],
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class TargetVersionEntity:
    """评测对象版本：发布后不可变的执行配置快照。"""

    id: str
    target_id: str
    version: int
    endpoint: str
    credential_ref: str | None = None
    invocation_config: dict[str, Any] = field(default_factory=dict)
    capabilities: list[dict[str, Any]] = field(default_factory=list)
    content_sha256: str = ""
    is_latest: bool = False
    published_at: datetime = field(default_factory=utcnow)

    @property
    def timeout_seconds(self) -> float:
        return float(self.invocation_config.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "target_id": self.target_id,
            "version": self.version,
            "endpoint": self.endpoint,
            "credential_ref": self.credential_ref,
            "invocation_config": dict(self.invocation_config),
            "capabilities": [dict(item) for item in self.capabilities],
            "content_sha256": self.content_sha256,
            "is_latest": self.is_latest,
            "published_at": self.published_at.isoformat(),
        }
