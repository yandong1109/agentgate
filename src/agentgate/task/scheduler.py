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

        # 真链路执行：复用 EvaluationService.launch（与「发起评测·运行评估」
        # 同一入口），获得完整评测闭环（快照固化/invoke/等 trace/评估/门槛）。
        # 真实 Run 会出现在 /api/runs 与结果报告页；task 侧 TaskRun/CaseExecution
        # 作为任务系统的执行留痕，统计从真实报告映射。
        real_run_id = ""
        error_message = ""
        try:
            from agentgate.server.application import get_evaluation_service

            evaluation_service = get_evaluation_service()
            if evaluation_service is None:
                raise RuntimeError("评测服务未初始化")

            evaluator_ids = [task.evaluator_id] if task.evaluator_id else None
            real_run = await asyncio.to_thread(
                evaluation_service.launch,
                task.target_id, task.dataset_id, None, evaluator_ids,
            )
            real_run_id = real_run.id

            # 从真实报告映射逐用例结果与统计（Result 为 domain 对象）
            report = evaluation_service.run_detail(real_run.id)
            by_case: dict[str, list] = {}
            for item in report.results:
                by_case.setdefault(item.case_id, []).append(item)

            completed_count = len(by_case)
            passed_count = 0
            total_score = 0.0
            for case_id, case_results in by_case.items():
                passed = all(
                    item.outcome in ("pass", "not_applicable")
                    for item in case_results
                )
                scores = [
                    item.score for item in case_results
                    if item.score is not None
                ]
                score = (sum(scores) / len(scores)) if scores else 0.0
                if passed:
                    passed_count += 1
                total_score += score
                summary = "; ".join(
                    f"{item.evaluator_name}:{item.outcome}"
                    for item in case_results
                ) or f"gate={report.gate.outcome}"
                from .domain import CaseExecution
                self.scheduler_service.repository.create_case_execution(
                    CaseExecution(
                        run_id=run.id,
                        case_id=case_id,
                        status=TaskStatus.SUCCESS if passed else TaskStatus.FAIL,
                        score=round(score * 100, 1),
                        passed=passed,
                        agent_response=summary,
                    )
                )
            run.completed_cases = completed_count
            run.passed_cases = passed_count
            run.failed_cases = completed_count - passed_count
            run.avg_score = (
                total_score / completed_count * 100 if completed_count else 0.0
            )
            if report.run.status != "completed":
                raise RuntimeError(
                    f"评测未完成: status={report.run.status}, "
                    f"error={report.run.error or ''}"
                )
        except Exception as exc:  # noqa: BLE001 - 任务失败须留痕不中断调度循环
            logger.error(f"任务 {task.id} 真链路执行失败: {exc}", exc_info=True)
            error_message = str(exc)

        if not error_message:
            # 执行完成
            run.status = TaskStatus.SUCCESS
            run.completed_at = utcnow()
            self.scheduler_service.repository.update_run(run)

            task.status = TaskStatus.SUCCESS
            task.updated_at = utcnow()
            self.scheduler_service.repository.update_task(task)
            logger.info(
                f"任务执行完成: {task.id}, run={run.run_no}, 真实Run={real_run_id[:8]}, "
                f"共 {run.completed_cases} 用例, {run.passed_cases} 通过"
            )
        else:
            run.status = TaskStatus.FAIL
            run.completed_at = utcnow()
            self.scheduler_service.repository.update_run(run)
            task.status = TaskStatus.FAIL
            task.updated_at = utcnow()
            self.scheduler_service.repository.update_task(task)

    async def _get_dataset_cases(self, dataset_id: str) -> list[dict]:
        """从数据集服务获取用例"""
        try:
            # 导入应用层来获取数据集服务
            from agentgate.server.application import get_datasets_service
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
