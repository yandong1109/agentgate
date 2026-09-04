"""
任务调度器模块。

实现后台定时扫描和执行 PENDING 状态任务的逻辑。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from .domain import TaskRun, TaskStatus, utcnow

# baibo加入
from ..Agent_Execute.Agent_execute import AgentExecutePerInvocation_id, Target, query_trace
# 结束

if TYPE_CHECKING:
    from .service import SchedulerService

logger = logging.getLogger(__name__)


class BackgroundScheduler:
    """后台任务调度器"""

    def __init__(self, scheduler_service: "SchedulerService", interval_seconds: int = 300):
        self.scheduler_service = scheduler_service
        self.interval = interval_seconds
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """启动调度器"""
        if self._running:
            logger.warning("调度器已在运行中")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"任务调度器已启动，扫描间隔: {self.interval}秒")

    async def _run_loop(self) -> None:
        """调度器主循环"""
        while self._running:
            try:
                await self._scan_and_execute()
            except Exception as e:
                logger.error(f"扫描和执行任务时出错: {e}", exc_info=True)

            await asyncio.sleep(self.interval)

    def stop(self) -> None:
        """停止调度器"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("任务调度器已停止")

    async def _scan_and_execute(self) -> None:
        """扫描 PENDING 任务并执行"""
        logger.info("开始扫描 PENDING 状态任务...")

        if not self.scheduler_service.repository:
            logger.warning("仓库未初始化，跳过扫描")
            return

        # 查询所有 PENDING 状态的任务
        tasks = self.scheduler_service.repository.list_tasks(status=TaskStatus.PENDING.value)
        logger.info(f"找到 {len(tasks)} 个待执行任务")

        for task in tasks:
            try:
                await self._execute_task(task)
            except Exception as e:
                logger.error(f"执行任务 {task.id} 失败: {e}", exc_info=True)
                # 更新任务状态为 FAIL
                try:
                    task.status = TaskStatus.FAIL
                    self.scheduler_service.repository.update_task(task)
                except Exception as update_err:
                    logger.error(f"更新任务状态失败: {update_err}")

    async def _execute_task(self, task) -> None:
        """执行单个任务"""
        logger.info(f"开始执行任务: {task.id}, 名称: {task.task_name}")

        if not self.scheduler_service.repository:
            logger.error("仓库未初始化，无法执行任务")
            task.status = TaskStatus.FAIL
            return

        # 获取已有的 TaskRun 记录（由 start_task API 创建）
        existing_runs = self.scheduler_service.repository.list_runs(task.id)
        if not existing_runs:
            logger.error(f"任务 {task.id} 没有执行记录，创建一个新的")
            run_no = 1
            run = TaskRun(
                task_id=task.id,
                run_no=run_no,
                status=TaskStatus.PENDING,
                target_snapshot_id=task.target_snapshot_id or "",
                dataset_snapshot_id=task.dataset_snapshot_id or "",
                evaluator_snapshot_id=task.evaluator_snapshot_id or "",
                total_cases=0,
            )
            self.scheduler_service.repository.create_run(run)
        else:
            # 使用最新的执行记录
            run = existing_runs[-1]
            logger.info(f"使用已有执行记录: run_id={run.id}, run_no={run.run_no}")

        # 状态变更：PENDING → RUNNING
        task.status = TaskStatus.RUNNING
        task.updated_at = utcnow()
        self.scheduler_service.repository.update_task(task)

        # 更新执行记录状态
        run.status = TaskStatus.RUNNING
        run.started_at = utcnow()
        self.scheduler_service.repository.update_run(run)

        logger.info(f"任务状态变更为 RUNNING: {task.id}")

        # 从数据集服务获取用例（通过内部调用）
        cases = await self._get_dataset_cases(task.dataset_id)
        logger.info(f"从数据集加载了 {len(cases)} 个用例")

        # 为每个用例创建执行记录
        completed_count = 0
        passed_count = 0
        total_score = 0.0

        # 插入agent启动相关代码-baibo 0902
        # 注意：变量名用 agent_exec，避免覆盖方法参数 task（TaskRecord）
        agent_exec = AgentExecutePerInvocation_id(
            invocation_id="invocation-001",
            idempotency_key="idempotency-001",
            target=Target(
                type="agent",
                id="agent-test-task",
                version_id="v1",
            ),
            run_id="run-001",
            case_id="case-001",
            turn_id="turn-001",
            input={"message": "请调研苏州市"},
            state={},
        )
        await asyncio.to_thread(agent_exec.start_agent_http_listening)
        await asyncio.to_thread(
            agent_exec.execute_agent_http,
            target=agent_exec.target,
            input=agent_exec.input,
            state=agent_exec.state,
            invocation_id=agent_exec.invocation_id,
        )
        await asyncio.to_thread(agent_exec.start_trace_server)
        await asyncio.to_thread(query_trace().get_trace, trace_id=agent_exec.invocation_id)
        # 结束

        for case in cases:
            from .domain import CaseExecution
            case_exec = CaseExecution(
                run_id=run.id,
                case_id=case["id"],
                status=TaskStatus.SUCCESS,
                score=85.0,
                passed=True,
                agent_response=f"模拟响应 for case: {case['name'] or case['id']}",
            )
            self.scheduler_service.repository.create_case_execution(case_exec)
            completed_count += 1
            passed_count += 1
            total_score += 85.0
            logger.info(f"用例执行完成: case_id={case_exec.case_id}, score={case_exec.score}")

        # 更新执行记录统计
        run.completed_cases = completed_count
        run.passed_cases = passed_count
        run.failed_cases = 0
        run.avg_score = total_score / len(cases) if cases else 0.0

        # 执行完成
        run.status = TaskStatus.SUCCESS
        run.completed_at = utcnow()
        self.scheduler_service.repository.update_run(run)

        # 更新任务最终状态
        task.status = TaskStatus.SUCCESS
        task.updated_at = utcnow()
        self.scheduler_service.repository.update_task(task)

        logger.info(f"任务执行完成: {task.id}, 共执行 {completed_count} 个用例")

    async def _get_dataset_cases(self, dataset_id: str) -> list[dict]:
        """从数据集服务获取用例"""
        try:
            # 导入应用层来获取数据集服务
            from src.agentgate.server.application import get_datasets_service
            datasets_service = get_datasets_service()
            if datasets_service:
                version = datasets_service.get_version(dataset_id, 1)
                if version and version.cases:
                    # 将 Pydantic Case 对象转换为字典
                    cases = []
                    for case in version.cases:
                        cases.append({
                            "id": case.id,
                            "name": case.name,
                            "turns": [
                                {
                                    "id": turn.id,
                                    "input": dict(turn.input) if hasattr(turn.input, '__dict__') else turn.input,
                                    "expected_skill": turn.expected_skill,
                                }
                                for turn in case.turns
                            ] if case.turns else [],
                        })
                    logger.info(f"通过数据集服务获取了 {len(cases)} 个用例")
                    return cases
        except Exception as e:
            logger.error(f"获取数据集用例失败: {e}", exc_info=True)
        return []
