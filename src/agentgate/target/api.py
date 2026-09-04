"""评测对象注册 API 路由（挂载于 /api 前缀下）。

约定：
- 成功响应使用 ``{code: 0, message, data}`` envelope（与 task 模块一致）；
- 错误响应使用 HTTPException（前端 request.ts 统一转为 ApiError）；
- 请求体中的密钥类字段一律 400 拒绝（安全红线）。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ValidationError

from .service import TargetError, TargetService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/targets", tags=["target"])

_target_service: TargetService | None = None

# 密钥类字段黑名单：密钥只能经环境变量注入（credential_ref 引用）
_FORBIDDEN_KEY_PARTS = ("api_key", "apikey", "secret", "token", "password")


def set_services(service: TargetService) -> None:
    """设置服务实例（由 create_app 装配时调用）"""
    global _target_service
    _target_service = service


def get_target_service() -> TargetService:
    if _target_service is None:
        raise HTTPException(status_code=503, detail="评测对象服务未初始化")
    return _target_service


class CapabilityItem(BaseModel):
    name: str
    kind: str = "tool"
    description: str = ""


class CreateTargetRequest(BaseModel):
    display_name: str
    endpoint: str
    target_type: str = "agent"
    adapter_type: str = "http"
    credential_ref: str | None = None
    platform_id: str = "registered"
    external_target_id: str | None = None
    description: str = ""
    capabilities: list[CapabilityItem] = []
    timeout_seconds: float | None = None


class UpdateTargetRequest(BaseModel):
    display_name: str | None = None
    description: str | None = None
    capabilities: list[CapabilityItem] | None = None


class PublishTargetVersionRequest(BaseModel):
    endpoint: str | None = None
    credential_ref: str | None = None
    capabilities: list[CapabilityItem] | None = None
    timeout_seconds: float | None = None


class TestConnectionRequest(BaseModel):
    endpoint: str | None = None
    credential_ref: str | None = None
    version: int | None = None
    timeout_seconds: float = 10.0


def _ok(data: Any) -> dict[str, Any]:
    return {"code": 0, "message": "success", "data": data}


def _reject_secret_fields(payload: dict[str, Any]) -> None:
    for key in payload:
        lowered = str(key).lower()
        if any(part in lowered for part in _FORBIDDEN_KEY_PARTS):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"请求字段 {key!r} 不允许：密钥请通过环境变量提供，"
                    "请求中只传 credential_ref（环境变量名）"
                ),
            )


def _parse(model_cls: type[BaseModel], payload: dict[str, Any]) -> BaseModel:
    try:
        return model_cls.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _call(action):
    """执行 service 动作并把 TargetError 映射为 HTTPException。"""
    try:
        return action()
    except TargetError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/test-connection")
def test_connection(payload: dict[str, Any]) -> dict[str, Any]:
    """临时连通性探测（注册向导中"测试连接"步骤，无需先注册）。"""
    _reject_secret_fields(payload)
    request = _parse(TestConnectionRequest, payload)
    service = get_target_service()
    return _ok(_call(lambda: service.test_connection(
        endpoint=request.endpoint,
        credential_ref=request.credential_ref,
        timeout_seconds=request.timeout_seconds,
    )))


@router.post("", status_code=201)
def register_target(payload: dict[str, Any]) -> dict[str, Any]:
    """注册评测对象（创建 + 自动发布 v1 不可变版本）。"""
    _reject_secret_fields(payload)
    request = _parse(CreateTargetRequest, payload)
    service = get_target_service()

    def _create():
        target, version = service.create_target(
            display_name=request.display_name,
            endpoint=request.endpoint,
            target_type=request.target_type,
            adapter_type=request.adapter_type,
            credential_ref=request.credential_ref,
            platform_id=request.platform_id,
            external_target_id=request.external_target_id,
            description=request.description,
            capabilities=[item.model_dump() for item in request.capabilities],
            timeout_seconds=request.timeout_seconds,
        )
        return {"target": target.to_dict(), "version": version.to_dict()}

    return _ok(_call(_create))


@router.get("")
def list_targets(type: str | None = None) -> dict[str, Any]:
    """评测对象列表（含最新版本摘要与版本数）；``?type=agent|skill`` 过滤。"""
    service = get_target_service()
    return _ok(_call(lambda: service.list_targets(type)))


@router.get("/{target_id}")
def get_target(target_id: str) -> dict[str, Any]:
    """评测对象详情（含全部已发布版本）。"""
    service = get_target_service()
    return _ok(_call(lambda: service.get_target(target_id)))


@router.patch("/{target_id}")
def update_target(target_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """更新可变元数据（展示名/描述/能力声明草稿）；执行配置走版本发布。"""
    _reject_secret_fields(payload)
    allowed = {"display_name", "description", "capabilities"}
    unknown = set(payload) - allowed
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"字段不允许修改（请发布新版本）: {', '.join(sorted(unknown))}",
        )
    request = _parse(UpdateTargetRequest, payload)
    service = get_target_service()

    def _update():
        target = service.update_target(
            target_id,
            display_name=request.display_name,
            description=request.description,
            capabilities=(
                [item.model_dump() for item in request.capabilities]
                if request.capabilities is not None else None
            ),
        )
        return target.to_dict()

    return _ok(_call(_update))


@router.delete("/{target_id}")
def delete_target(target_id: str) -> dict[str, Any]:
    """软删除；被运行记录引用时返回 409。"""
    service = get_target_service()
    return _ok(_call(lambda: service.delete_target(target_id)))


@router.post("/{target_id}/versions", status_code=201)
def publish_version(target_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """发布新版本（未指定字段继承上一版本；内容哈希随之固化）。"""
    _reject_secret_fields(payload)
    request = _parse(PublishTargetVersionRequest, payload)
    service = get_target_service()

    def _publish():
        version = service.publish_version(
            target_id,
            endpoint=request.endpoint,
            credential_ref=request.credential_ref,
            capabilities=(
                [item.model_dump() for item in request.capabilities]
                if request.capabilities is not None else None
            ),
            timeout_seconds=request.timeout_seconds,
        )
        return version.to_dict()

    return _ok(_call(_publish))


@router.post("/{target_id}/test-connection")
def test_target_connection(
    target_id: str, payload: dict[str, Any],
) -> dict[str, Any]:
    """对已注册评测对象做连通性测试（默认最新版本，可指定版本号）。"""
    _reject_secret_fields(payload)
    request = _parse(TestConnectionRequest, payload)
    service = get_target_service()
    return _ok(_call(lambda: service.test_target_connection(
        target_id, version=request.version,
    )))
