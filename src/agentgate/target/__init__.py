"""评测对象注册模块：注册、配置、版本化 Agent 目标（含端点、认证、能力声明）。"""

from .domain import (
    TargetEntity,
    TargetVersionEntity,
    TARGET_STATUS_ACTIVE,
    TARGET_STATUS_DELETED,
    compute_content_sha256,
)
from .repository import TargetRepository
from .service import TargetService

__all__ = [
    "TargetEntity",
    "TargetVersionEntity",
    "TargetRepository",
    "TargetService",
    "TARGET_STATUS_ACTIVE",
    "TARGET_STATUS_DELETED",
    "compute_content_sha256",
]
