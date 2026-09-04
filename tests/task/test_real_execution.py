"""任务真链路执行集成测试：创建 → 启动 → 调度器执行 → 断言真实评测结果。

覆盖 BackgroundScheduler._execute_task 复用 EvaluationService.launch 的真链路
（与「发起评测·运行评估」同一入口），替换此前的硬编码 demo + 伪造结果。
使用 demo 目标（loan-agent-v2-fixed，python_fn 内联 trace）——零外部依赖。
"""

import asyncio

from fastapi.testclient import TestClient

from agentgate.server.application import create_app
from agentgate.task.api import get_scheduler_service
from agentgate.task.scheduler import BackgroundScheduler


def _create_and_start_task(client: TestClient, **overrides) -> str:
    payload = {
        "task_name": "真链路任务",
        "target_id": "loan-agent-v2-fixed",
        "dataset_id": "loan-risk-policy",
        "evaluator_id": "required-tool",
        "created_by": "test",
    }
    payload.update(overrides)
    response = client.post("/api/tasks", json=payload)
    assert response.status_code == 201, response.text
    task_id = response.json()["data"]["id"]

    response = client.post(f"/api/tasks/{task_id}/start")
    assert response.status_code == 200, response.text
    return task_id


def _execute_once(task_id: str) -> None:
    scheduler = get_scheduler_service()
    worker = BackgroundScheduler(scheduler)
    task = scheduler.repository.get_task(task_id)
    asyncio.run(worker._execute_task(task))  # noqa: SLF001 - 测试直达执行体


def test_task_executes_real_evaluation_pipeline(tmp_path):
    with TestClient(create_app(tmp_path / "task-real.db")) as client:
        task_id = _create_and_start_task(client)
        _execute_once(task_id)

        scheduler = get_scheduler_service()

        # 任务与执行记录收敛 SUCCESS，统计来自真实报告
        task = scheduler.repository.get_task(task_id)
        assert task.status.value == "SUCCESS"
        run = scheduler.repository.list_runs(task_id)[-1]
        assert run.status.value == "SUCCESS"
        assert run.completed_cases >= 1
        assert run.passed_cases == run.completed_cases  # fixed 版全过
        assert run.failed_cases == 0
        assert run.avg_score == 100.0  # 不是伪造的 85.0

        # 逐用例执行记录为真实评估结果（评分器名:结果 摘要）
        case_execs = scheduler.repository.list_case_executions(run.id)
        assert len(case_execs) == run.completed_cases
        for item in case_execs:
            assert item["passed"] is True
            assert "必需工具" in item["agent_response"]
            assert item["score"] == 100.0

        # 真实 Run 已入库且完成（出现在运行记录/结果报告页）
        real_runs = client.get("/api/runs").json()
        mine = [
            r for r in real_runs
            if r["snapshot"]["target"]["ref"]["external_version_id"]
            == "loan-agent-v2-fixed"
        ]
        assert mine, "真实 Run 未落库"
        report = client.get(f"/api/runs/{mine[0]['id']}").json()
        assert report["run"]["status"] == "completed"
        assert report["gate"]["outcome"] == "pass"
        assert len(report["results"]) >= run.completed_cases


def test_task_failure_marks_fail_without_fake_success(tmp_path):
    """死端点目标：任务 FAIL（不再是伪造 SUCCESS），真实失败 Run 留痕。"""
    with TestClient(create_app(tmp_path / "task-fail.db")) as client:
        task_id = _create_and_start_task(
            client, task_name="死端点任务", target_id="langchain-http-agent",
        )
        _execute_once(task_id)

        scheduler = get_scheduler_service()
        task = scheduler.repository.get_task(task_id)
        assert task.status.value == "FAIL"

        run = scheduler.repository.list_runs(task_id)[-1]
        assert run.status.value == "FAIL"
        assert run.completed_cases == 0
        assert scheduler.repository.list_case_executions(run.id) == []

        # 引擎的失败 Run 也已留痕（可解释性）
        real_runs = client.get("/api/runs").json()
        assert any(
            r["status"] == "failed" and
            r["snapshot"]["target"]["ref"]["external_target_id"]
            == "langchain-agent"
            for r in real_runs
        )


def test_task_with_unknown_evaluator_fails(tmp_path):
    """未知评估器：launch 抛错 → 任务 FAIL（错误可见，而非静默成功）。"""
    with TestClient(create_app(tmp_path / "task-bad-evaluator.db")) as client:
        task_id = _create_and_start_task(
            client, task_name="坏评估器任务", evaluator_id="nonexistent-evaluator",
        )
        _execute_once(task_id)
        scheduler = get_scheduler_service()
        assert scheduler.repository.get_task(task_id).status.value == "FAIL"
