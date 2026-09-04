"""
Service tests.
"""

import pytest
from agentgate.task.domain import TaskStatus
from agentgate.task.service import SchedulerService, TaskExecutionService


def test_scheduler_service_create_task():
    """测试创建任务"""
    service = SchedulerService()

    task = service.create_task(
        task_name="Test Task",
        target_id="target-123",
        dataset_id="dataset-456",
        evaluator_id="evaluator-789",
        created_by="admin",
    )

    assert task.task_name == "Test Task"
    assert task.target_id == "target-123"
    assert task.dataset_id == "dataset-456"
    assert task.evaluator_id == "evaluator-789"
    assert task.status == TaskStatus.NEW
    assert task.created_by == "admin"


def test_scheduler_service_start_task():
    """测试启动任务"""
    service = SchedulerService()

    task = service.create_task(
        task_name="Test Task",
        target_id="target-123",
        dataset_id="dataset-456",
        evaluator_id="evaluator-789",
    )

    task = service.start_task(task)

    assert task.status == TaskStatus.PENDING


def test_scheduler_service_start_task_invalid_status():
    """测试启动任务 - 无效状态"""
    service = SchedulerService()

    task = service.create_task(
        task_name="Test Task",
        target_id="target-123",
        dataset_id="dataset-456",
        evaluator_id="evaluator-789",
    )

    task.status = TaskStatus.RUNNING

    with pytest.raises(ValueError):
        service.start_task(task)


def test_scheduler_service_stop_task():
    """测试停止任务"""
    service = SchedulerService()

    task = service.create_task(
        task_name="Test Task",
        target_id="target-123",
        dataset_id="dataset-456",
        evaluator_id="evaluator-789",
    )

    task.status = TaskStatus.PENDING
    task = service.stop_task(task, "admin")

    assert task.status == TaskStatus.TERMINATED


def test_scheduler_service_stop_task_invalid_status():
    """测试停止任务 - 无效状态"""
    service = SchedulerService()

    task = service.create_task(
        task_name="Test Task",
        target_id="target-123",
        dataset_id="dataset-456",
        evaluator_id="evaluator-789",
    )

    task.status = TaskStatus.SUCCESS

    with pytest.raises(ValueError):
        service.stop_task(task, "admin")


def test_task_execution_service():
    """测试任务执行服务"""
    scheduler = SchedulerService()
    execution_service = TaskExecutionService(scheduler)

    task = scheduler.create_task(
        task_name="Test Task",
        target_id="target-123",
        dataset_id="dataset-456",
        evaluator_id="evaluator-789",
    )

    run = execution_service.execute_task(task)

    assert run.task_id == task.id
    assert run.status == TaskStatus.RUNNING
    assert task.status == TaskStatus.RUNNING


def test_task_execution_service_cancel():
    """测试取消任务"""
    scheduler = SchedulerService()
    execution_service = TaskExecutionService(scheduler)

    task = scheduler.create_task(
        task_name="Test Task",
        target_id="target-123",
        dataset_id="dataset-456",
        evaluator_id="evaluator-789",
    )

    execution_service.cancel_task(task)
