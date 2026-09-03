"""
任务调度API路由模块。

提供FastAPI路由实现。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from .domain import (
    CaseExecution, EvalTask, TaskRun, TaskStatus,
    TargetAgentEntity,
)
from agentgate.domain.case import Dataset, Case
from .service import SchedulerService, TaskExecutionService

logger = logging.getLogger(__name__)

# Note: This router is meant to be mounted under /api prefix in the main application
# Route paths here should NOT include /tasks prefix since the router adds it
router = APIRouter(prefix="/tasks", tags=["task"])

# Separate router for execution-related routes that don't follow /tasks/{id} pattern
execution_router = APIRouter(prefix="", tags=["execution"])

_scheduler_service: SchedulerService | None = None
_execution_service: TaskExecutionService | None = None


def set_services(scheduler: SchedulerService, execution: TaskExecutionService) -> None:
    """设置服务实例"""
    global _scheduler_service, _execution_service
    _scheduler_service = scheduler
    _execution_service = execution


def get_scheduler_service() -> SchedulerService:
    """获取调度服务"""
    if _scheduler_service is None:
        return SchedulerService()
    return _scheduler_service


def get_execution_service() -> TaskExecutionService:
    """获取执行服务"""
    if _execution_service is None:
        scheduler = get_scheduler_service()
        return TaskExecutionService(scheduler)
    return _execution_service


@router.post("", status_code=201)
async def create_task(request: dict[str, Any]) -> dict[str, Any]:
    """创建任务"""
    scheduler = get_scheduler_service()

    task = scheduler.create_task(
        task_name=request.get("task_name", ""),
        target_id=request.get("target_id", ""),
        dataset_id=request.get("dataset_id", ""),
        evaluator_id=request.get("evaluator_id", ""),
        created_by=request.get("created_by", ""),
    )

    # 保存到数据库
    if scheduler.repository:
        scheduler.repository.create_task(task)

    return {
        "code": 0,
        "message": "success",
        "data": task.to_dict(),
    }


@router.get("")
async def list_tasks(
    status: str | None = None,
    target_id: str | None = None,
    page: int = 0,
    size: int = 10,
) -> dict[str, Any]:
    """查询任务列表"""
    scheduler = get_scheduler_service()

    tasks = []
    total_elements = 0
    if scheduler.repository:
        tasks = scheduler.repository.list_tasks(
            status=status,
            target_id=target_id,
            page=page,
            size=size,
        )
        total_elements = scheduler.repository.count_tasks(
            status=status,
            target_id=target_id,
        )

    total_pages = (total_elements + size - 1) // size if total_elements > 0 else 0

    return {
        "code": 0,
        "message": "success",
        "data": {
            "content": [t.to_dict() for t in tasks],
            "total_elements": total_elements,
            "total_pages": total_pages,
            "page": page,
            "size": size,
        },
    }


@router.get("/{task_id}")
async def get_task(task_id: str) -> dict[str, Any]:
    """查询任务详情"""
    scheduler = get_scheduler_service()

    if scheduler.repository:
        task = scheduler.repository.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
    else:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "code": 0,
        "message": "success",
        "data": task.to_dict(),
    }


@router.post("/{task_id}/start")
async def start_task(task_id: str) -> dict[str, Any]:
    """启动任务（同时创建快照和执行记录）"""
    scheduler = get_scheduler_service()

    if scheduler.repository:
        task = scheduler.repository.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        try:
            # 获取数据集版本信息（包含所有Case和CaseTurn）
            dataset_version_info = _get_dataset_version(task.dataset_id)
            cases_data = dataset_version_info.get("cases", [])
            case_count = len(cases_data)

            # 获取评测对象信息并创建快照
            target_info = _get_target_info(task.target_id)
            target_snapshot_id = scheduler.repository.create_target_snapshot(
                target_id=task.target_id,
                agent_name=target_info.get("agent_name", ""),
                agent_type=target_info.get("agent_type", "REMOTE_AGENT"),
                config=target_info.get("config", {}),
                status=target_info.get("status", "ACTIVE"),
            )

            # 获取测评集信息并创建快照
            dataset_info = dataset_version_info.get("dataset", {})
            dataset_snapshot_id = scheduler.repository.create_dataset_snapshot(
                dataset_id=task.dataset_id,
                name=dataset_info.get("name", ""),
                description=dataset_info.get("description", ""),
                purpose=dataset_info.get("purpose", "standard"),
                archived=dataset_info.get("archived", False),
            )

            # 评估器快照
            evaluator_snapshot_id = scheduler.repository.create_evaluator_snapshot(
                evaluator_id=task.evaluator_id,
                snapshot_data={"evaluator_id": task.evaluator_id},
            )

            # 保存快照ID到任务
            task.target_snapshot_id = target_snapshot_id
            task.dataset_snapshot_id = dataset_snapshot_id
            task.evaluator_snapshot_id = evaluator_snapshot_id

            # 启动任务 - 状态变为 PENDING
            task = scheduler.start_task(task)
            scheduler.repository.update_task(task)

            # 创建任务执行记录 TaskRun
            existing_runs = scheduler.repository.list_runs(task.id)
            run_no = max([r.run_no for r in existing_runs], default=0) + 1

            from .domain import TaskRun, TaskStatus, utcnow
            run = TaskRun(
                task_id=task.id,
                run_no=run_no,
                status=TaskStatus.PENDING,
                target_snapshot_id=target_snapshot_id,
                dataset_snapshot_id=dataset_snapshot_id,
                evaluator_snapshot_id=evaluator_snapshot_id,
                total_cases=case_count if case_count > 0 else 1,
            )
            scheduler.repository.create_run(run)

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "code": 0,
        "message": "success",
        "data": {
            "task_id": task.id,
            "status": task.status.value if hasattr(task.status, "value") else task.status,
            "target_snapshot_id": task.target_snapshot_id,
            "dataset_snapshot_id": task.dataset_snapshot_id,
            "evaluator_snapshot_id": task.evaluator_snapshot_id,
            "message": "任务已启动，快照已创建，等待调度执行",
        },
    }


@router.post("/{task_id}/stop")
async def stop_task(task_id: str, request: dict[str, Any] | None = None) -> dict[str, Any]:
    """停止任务（人工终止）"""
    scheduler = get_scheduler_service()

    if scheduler.repository:
        task = scheduler.repository.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        terminated_by = request.get("reason", "") if request else ""
        try:
            task = scheduler.stop_task(task, terminated_by)
            scheduler.repository.update_task(task)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "code": 0,
        "message": "success",
        "data": {
            "task_id": task.id,
            "status": task.status.value if hasattr(task.status, "value") else task.status,
            "terminated_by": terminated_by,
        },
    }


@router.post("/{task_id}/rerun")
async def rerun_task(task_id: str) -> dict[str, Any]:
    """任务重新执行"""
    scheduler = get_scheduler_service()

    runs = []
    if scheduler.repository:
        task = scheduler.repository.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        runs = scheduler.repository.list_runs(task_id)
        if not runs:
            raise HTTPException(status_code=400, detail="任务必须已有执行记录")
    else:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "code": 0,
        "message": "success",
        "data": {
            "run_id": "",
            "run_no": len(runs) + 1,
            "status": "NEW",
            "message": "新执行记录已创建",
        },
    }


@router.delete("/{task_id}")
async def delete_task(task_id: str) -> dict[str, Any]:
    """删除任务"""
    scheduler = get_scheduler_service()

    if scheduler.repository:
        task = scheduler.repository.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if task.status not in [TaskStatus.NEW, TaskStatus.SUCCESS, TaskStatus.FAIL, TaskStatus.TERMINATED]:
            raise HTTPException(status_code=400, detail="任务状态不允许此操作")

        scheduler.repository.delete_task(task_id)
    else:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "code": 0,
        "message": "success",
    }


@router.get("/{task_id}/runs")
async def list_runs(task_id: str) -> dict[str, Any]:
    """查询执行记录列表"""
    scheduler = get_scheduler_service()

    runs = []
    if scheduler.repository:
        runs = scheduler.repository.list_runs(task_id)

    return {
        "code": 0,
        "message": "success",
        "data": [r.to_dict() for r in runs],
    }


# 快照查询路由（独立路径，不在tasks下）
@router.get("/snapshots/target/{snapshot_id}")
async def get_target_snapshot(snapshot_id: str) -> dict[str, Any]:
    """获取智能体快照"""
    scheduler = get_scheduler_service()

    if scheduler.repository:
        snapshot = scheduler.repository.get_target_snapshot(snapshot_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        return {"code": 0, "message": "success", "data": snapshot}
    raise HTTPException(status_code=404, detail="Repository not available")


@router.get("/snapshots/dataset/{snapshot_id}")
async def get_dataset_snapshot(snapshot_id: str) -> dict[str, Any]:
    """获取测评集快照"""
    scheduler = get_scheduler_service()

    if scheduler.repository:
        snapshot = scheduler.repository.get_dataset_snapshot(snapshot_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        return {"code": 0, "message": "success", "data": snapshot}
    raise HTTPException(status_code=404, detail="Repository not available")


@router.get("/snapshots/evaluator/{snapshot_id}")
async def get_evaluator_snapshot(snapshot_id: str) -> dict[str, Any]:
    """获取评估器快照"""
    scheduler = get_scheduler_service()

    if scheduler.repository:
        snapshot = scheduler.repository.get_evaluator_snapshot(snapshot_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        return {"code": 0, "message": "success", "data": snapshot}
    raise HTTPException(status_code=404, detail="Repository not available")


@router.get("/cases/{case_id}")
async def get_case(case_id: str) -> dict[str, Any]:
    """获取用例详情"""
    scheduler = get_scheduler_service()

    if scheduler.repository:
        case = scheduler.repository.get_case(case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        return {"code": 0, "message": "success", "data": case}
    raise HTTPException(status_code=404, detail="Repository not available")


@router.get("/runs/{run_id}/cases")
async def list_run_cases(run_id: str) -> dict[str, Any]:
    """查询执行记录下的用例执行列表"""
    scheduler = get_scheduler_service()

    if scheduler.repository:
        cases = scheduler.repository.list_case_executions(run_id)
        return {"code": 0, "message": "success", "data": cases}
    raise HTTPException(status_code=404, detail="Repository not available")


def _get_dataset_version(dataset_id: str) -> dict:
    """从数据集服务获取完整的数据集版本信息"""
    try:
        from src.agentgate.server.application import get_datasets_service
        datasets_service = get_datasets_service()
        if datasets_service:
            version = datasets_service.get_version(dataset_id, 1)
            if version:
                # 返回数据集信息和用例列表
                return {
                    "dataset": {
                        "id": dataset_id,
                        "name": getattr(version, "dataset_name", ""),
                        "description": getattr(version, "dataset_description", ""),
                        "purpose": "standard",
                        "archived": False,
                    },
                    "cases": [
                        {
                            "id": case.id,
                            "name": getattr(case, "name", ""),
                            "initial_state": getattr(case, "initial_state", {}),
                            "category": str(getattr(case, "category", "positive")),
                            "difficulty": str(getattr(case, "difficulty", "medium")),
                            "tags": ",".join(getattr(case, "tags", [])),
                            "notes": getattr(case, "notes", ""),
                            "turns": _get_case_turns(case),
                        }
                        for case in (version.cases or [])
                    ],
                }
    except Exception as e:
        logger.error(f"获取数据集版本失败: {e}")
    return {"dataset": {}, "cases": []}


def _get_case_turns(case: Any) -> list:
    """从Case对象中提取CaseTurn信息"""
    try:
        turns = getattr(case, "turns", []) or []
        return [
            {
                "id": getattr(turn, "id", ""),
                "input": dict(getattr(turn, "input", {})),
                "expected_skill": getattr(turn, "expected_skill", "") or "",
                "expectations": ",".join([
                    exp.model_dump_json() if hasattr(exp, "model_dump_json") else str(exp)
                    for exp in (getattr(turn, "expectations", []) or [])
                ]),
                "required_tools": ",".join(getattr(turn, "required_tools", []) or []),
                "forbidden_tools": ",".join(getattr(turn, "forbidden_tools", []) or []),
                "policy_rules": ",".join(getattr(turn, "policy_rules", []) or []),
                "notes": getattr(turn, "notes", "") or "",
            }
            for turn in turns
        ]
    except Exception as e:
        logger.error(f"获取用例轮次失败: {e}")
        return []


def _get_target_info(target_id: str) -> dict:
    """从评测对象服务获取评测对象信息（S3：切换到 target 模块数据源）。

    数据源说明：优先经 target 服务解析（支持版本键，如 "my-agent-v1"）；
    解析失败时返回与旧行为一致的回退结构，仅记录告警不再静默吞错。
    """
    try:
        from agentgate.target import api as target_api

        service = target_api.get_target_service()
        return service.get_target_info(target_id)
    except Exception as e:
        logger.warning(f"获取评测对象信息失败，使用回退配置: {e}")
        return {
            "agent_name": target_id,
            "agent_type": "REMOTE_AGENT",
            "config": {},
            "status": "ACTIVE",
        }
