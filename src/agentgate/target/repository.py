"""评测对象注册持久化层（SQLAlchemy）。

表结构为纯增量新增（``eval_target`` / ``eval_target_version``），
旧代码遇到新表会直接忽略——回退代码无需回退数据。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Callable

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

from .domain import (
    TARGET_STATUS_ACTIVE,
    TargetEntity,
    TargetVersionEntity,
    utcnow,
)

logger = logging.getLogger(__name__)

Base = declarative_base()


class TargetModel(Base):
    """评测对象注册表"""

    __tablename__ = "eval_target"

    id = Column(String(36), primary_key=True)
    display_name = Column(String(255), nullable=False)
    target_type = Column(String(32), nullable=False)
    adapter_type = Column(String(32), nullable=False)
    external_target_id = Column(String(255), nullable=False, unique=True)
    platform_id = Column(String(64), default="registered")
    description = Column(Text, default="")
    capabilities = Column(JSON, default=list)
    status = Column(String(32), default=TARGET_STATUS_ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TargetVersionModel(Base):
    """评测对象版本表（发布后不可变；每对象至多一个 is_latest）"""

    __tablename__ = "eval_target_version"
    __table_args__ = (
        UniqueConstraint("target_id", "version", name="uq_eval_target_version"),
    )

    id = Column(String(36), primary_key=True)
    target_id = Column(
        String(36), ForeignKey("eval_target.id"), nullable=False, index=True
    )
    version = Column(Integer, nullable=False)
    endpoint = Column(String(1024), nullable=False)
    credential_ref = Column(String(255), nullable=True)
    invocation_config = Column(JSON, default=dict)
    capabilities = Column(JSON, default=list)
    content_sha256 = Column(String(64), nullable=False)
    is_latest = Column(Boolean, default=False)
    published_at = Column(DateTime, default=datetime.utcnow)


def _to_entity(row: TargetModel) -> TargetEntity:
    return TargetEntity(
        id=row.id,
        display_name=row.display_name,
        target_type=row.target_type,
        adapter_type=row.adapter_type,
        external_target_id=row.external_target_id,
        platform_id=row.platform_id or "registered",
        description=row.description or "",
        capabilities=list(row.capabilities or []),
        status=row.status or TARGET_STATUS_ACTIVE,
        created_at=row.created_at or datetime.now(UTC),
        updated_at=row.updated_at or datetime.now(UTC),
    )


def _to_version_entity(row: TargetVersionModel) -> TargetVersionEntity:
    return TargetVersionEntity(
        id=row.id,
        target_id=row.target_id,
        version=row.version,
        endpoint=row.endpoint,
        credential_ref=row.credential_ref,
        invocation_config=dict(row.invocation_config or {}),
        capabilities=list(row.capabilities or []),
        content_sha256=row.content_sha256,
        is_latest=bool(row.is_latest),
        published_at=row.published_at or datetime.now(UTC),
    )


class TargetRepository:
    """session-per-operation 仓储；线程安全（配合 check_same_thread=False 引擎）。"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ── Target ────────────────────────────────────────────────

    def create_target(self, entity: TargetEntity) -> TargetEntity:
        with self._session_factory() as session:
            session.add(TargetModel(
                id=entity.id,
                display_name=entity.display_name,
                target_type=entity.target_type,
                adapter_type=entity.adapter_type,
                external_target_id=entity.external_target_id,
                platform_id=entity.platform_id,
                description=entity.description,
                capabilities=list(entity.capabilities),
                status=entity.status,
                created_at=entity.created_at,
                updated_at=entity.updated_at,
            ))
            session.commit()
        return entity

    def get_target(self, target_id: str) -> TargetEntity | None:
        with self._session_factory() as session:
            row = session.get(TargetModel, target_id)
            return _to_entity(row) if row is not None else None

    def get_target_by_external_id(self, external_target_id: str) -> TargetEntity | None:
        with self._session_factory() as session:
            row = (
                session.query(TargetModel)
                .filter(TargetModel.external_target_id == external_target_id)
                .one_or_none()
            )
            return _to_entity(row) if row is not None else None

    def list_targets(self, active_only: bool = True) -> list[TargetEntity]:
        with self._session_factory() as session:
            query = session.query(TargetModel)
            if active_only:
                query = query.filter(TargetModel.status == TARGET_STATUS_ACTIVE)
            rows = query.order_by(TargetModel.created_at).all()
            return [_to_entity(row) for row in rows]

    def update_target(self, entity: TargetEntity) -> TargetEntity:
        entity.updated_at = utcnow()
        with self._session_factory() as session:
            row = session.get(TargetModel, entity.id)
            if row is None:
                raise LookupError(f"target not found: {entity.id}")
            row.display_name = entity.display_name
            row.description = entity.description
            row.capabilities = list(entity.capabilities)
            row.external_target_id = entity.external_target_id
            row.status = entity.status
            row.updated_at = entity.updated_at
            session.commit()
        return entity

    # ── Version ───────────────────────────────────────────────

    def list_versions(self, target_id: str) -> list[TargetVersionEntity]:
        with self._session_factory() as session:
            rows = (
                session.query(TargetVersionModel)
                .filter(TargetVersionModel.target_id == target_id)
                .order_by(TargetVersionModel.version.desc())
                .all()
            )
            return [_to_version_entity(row) for row in rows]

    def get_version(self, target_id: str, version: int) -> TargetVersionEntity | None:
        with self._session_factory() as session:
            row = (
                session.query(TargetVersionModel)
                .filter(
                    TargetVersionModel.target_id == target_id,
                    TargetVersionModel.version == version,
                )
                .one_or_none()
            )
            return _to_version_entity(row) if row is not None else None

    def get_latest_version(self, target_id: str) -> TargetVersionEntity | None:
        with self._session_factory() as session:
            row = (
                session.query(TargetVersionModel)
                .filter(
                    TargetVersionModel.target_id == target_id,
                    TargetVersionModel.is_latest.is_(True),
                )
                .one_or_none()
            )
            return _to_version_entity(row) if row is not None else None

    def insert_version(self, entity: TargetVersionEntity) -> TargetVersionEntity:
        """插入新版本并在同一事务中迁移 is_latest 标记。"""
        with self._session_factory() as session:
            session.query(TargetVersionModel).filter(
                TargetVersionModel.target_id == entity.target_id,
                TargetVersionModel.is_latest.is_(True),
            ).update({"is_latest": False})
            session.add(TargetVersionModel(
                id=entity.id,
                target_id=entity.target_id,
                version=entity.version,
                endpoint=entity.endpoint,
                credential_ref=entity.credential_ref,
                invocation_config=dict(entity.invocation_config),
                capabilities=list(entity.capabilities),
                content_sha256=entity.content_sha256,
                is_latest=True,
                published_at=entity.published_at,
            ))
            session.commit()
        return entity
