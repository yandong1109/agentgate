"""
任务调度服务模块。

提供任务编排、调度执行、状态流转等服务。
"""

from __future__ import annotations

import logging
from datetime import datetime, UTC
from typing import TYPE_CHECKING

from .agent import TargetAgentFactory
from .domain import (
    AgentType, CaseExecution, DatasetSnapshot, EvaluatorEntity,
    EvaluationResult, EvaluationResultEntity, EvalTask, TaskRun, TaskStatus,
    TargetAgentEntity, TargetSnapshot, utcnow,
)
from agentgate.domain.case import Dataset, Case
from .evaluator import EvaluatorFactory

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SchedulerService:
    """任务调度服务"""

    def __init__(self, repository: "TaskRepository | None" = None):
        self.repository = repository
        self._scheduler: "BackgroundScheduler | None" = None

    async def start_scheduler(self, interval_seconds: int = 300) -> None:
        """启动后台调度器"""
        if self._scheduler and self._scheduler._running:
            logger.warning("调度器已在运行中")
            return

        from .scheduler import BackgroundScheduler
        self._scheduler = BackgroundScheduler(self, interval_seconds)
        await self._scheduler.start()
        logger.info(f"调度器已启动，间隔: {interval_seconds}秒")

    def stop_scheduler(self) -> None:
        """停止后台调度器"""
        if self._scheduler:
            self._scheduler.stop()
            self._scheduler = None
            logger.info("调度器已停止")

    def create_task(
        self,
        task_name: str,
        target_id: str,
        dataset_id: str,
        evaluator_id: str,
        created_by: str = "",
    ) -> EvalTask:
        """
        创建评测任务
        :param task_name: 任务名称
        :param target_id: 智能体ID
        :param dataset_id: 测评集ID
        :param evaluator_id: 评估器ID
        :param created_by: 创建人
        :return: 创建的任务
        """
        task = EvalTask(
            task_name=task_name,
            target_id=target_id,
            dataset_id=dataset_id,
            evaluator_id=evaluator_id,
            status=TaskStatus.NEW,
            created_by=created_by,
        )
        logger.info(f"Created task: {task.id}, name: {task_name}")
        return task

    def start_task(self, task: EvalTask) -> EvalTask:
        """
        启动任务
        :param task: 任务
        :return: 更新后的任务
        """
        if task.status != TaskStatus.NEW:
            raise ValueError(f"任务状态不允许此操作，当前状态：{task.status}")

        task.status = TaskStatus.PENDING
        task.updated_at = utcnow()
        logger.info(f"Task {task.id} started, status changed to PENDING")
        return task

    def stop_task(self, task: EvalTask, terminated_by: str = "") -> EvalTask:
        """
        停止任务（人工终止）
        :param task: 任务
        :param terminated_by: 终止操作人
        :return: 更新后的任务
        """
        if task.status not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            raise ValueError(f"任务状态不允许此操作，当前状态：{task.status}")

        task.status = TaskStatus.TERMINATED
        task.updated_at = utcnow()
        logger.info(f"Task {task.id} stopped by {terminated_by}")
        return task

    def get_next_pending_task(self) -> EvalTask | None:
        """获取下一个待执行的任务"""
        return None


class TaskExecutionService:
    """任务执行服务"""

    def __init__(self, scheduler_service: SchedulerService):
        self.scheduler_service = scheduler_service
        self._running_tasks: dict[str, "TaskRunner"] = {}

    def execute_task(self, task: EvalTask) -> TaskRun:
        """
        执行任务
        :param task: 任务
        :return: 执行记录
        """
        logger.info(f"Starting execution for task: {task.id}")

        task.status = TaskStatus.RUNNING
        task.updated_at = utcnow()

        run = TaskRun(
            task_id=task.id,
            run_no=1,
            status=TaskStatus.RUNNING,
            total_cases=0,
        )

        logger.info(f"Task execution started, run_id: {run.id}")
        return run

    def execute_case(
        self,
        run: TaskRun,
        case: "Case",
        target: TargetAgentEntity,
        evaluator: EvaluatorEntity,
    ) -> CaseExecution:
        """
        执行单个用例
        :param run: 执行记录
        :param case: 测试用例
        :param target: 智能体
        :param evaluator: 评估器
        :return: 用例执行记录
        """
        execution = CaseExecution(
            run_id=run.id,
            case_id=case.id,
            status=TaskStatus.RUNNING,
        )

        try:
            agent_executor = TargetAgentFactory.create(
                target.agent_type, target.config
            )
            agent_executor.initialize()

            dialog_rounds = case.dialog_rounds
            all_responses = []

            for round_data in dialog_rounds:
                user_input = round_data.get("user_input", "")
                response = agent_executor.send_query(user_input)
                all_responses.append({
                    "round": round_data.get("round", 1),
                    "user_input": user_input,
                    "agent_response": response,
                })

            execution.agent_response = "\n".join([r["agent_response"] for r in all_responses])
            execution.trace_data = all_responses

            trace_info = agent_executor.get_trace()
            execution.trace_data = {
                "session_id": trace_info.session_id,
                "rounds": trace_info.rounds,
                "tool_calls": trace_info.tool_calls,
            }

            agent_executor.close()

            eval_instance = EvaluatorFactory.create(
                evaluator.evaluator_type, evaluator.config
            )
            eval_result = eval_instance.calculate(execution)

            execution.score = eval_result.score
            execution.passed = eval_result.passed
            execution.status = TaskStatus.SUCCESS
            execution.evaluation_result_id = eval_result.details.get("result_id", "")

        except Exception as e:
            logger.error(f"Case execution failed: {e}")
            execution.status = TaskStatus.FAIL
            execution.score = 0.0
            execution.passed = False

        execution.completed_at = utcnow()
        return execution

    def cancel_task(self, task: EvalTask) -> None:
        """
        取消任务
        :param task: 任务
        """
        if task.id in self._running_tasks:
            runner = self._running_tasks[task.id]
            runner.stop()
            del self._running_tasks[task.id]
            logger.info(f"Task {task.id} cancelled")


class TaskRunner:
    """任务运行器（用于后台执行）"""

    def __init__(self, task: EvalTask, execution_service: TaskExecutionService):
        self.task = task
        self.execution_service = execution_service
        self._stopped = False

    def run(self) -> TaskRun:
        """执行任务"""
        return self.execution_service.execute_task(self.task)

    def stop(self) -> None:
        """停止执行"""
        self._stopped = True
        logger.info(f"Task runner for {self.task.id} stopped")
