"""
任务接口时区测试。
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from agentgate.server.application import create_app


BEIJING_TZ = timezone(timedelta(hours=8))


def test_create_task_returns_beijing_time(tmp_path):
    """测试通过API创建任务，查询出的created_at时间是北京时间"""
    with TestClient(create_app(tmp_path / "task_timezone.db")) as client:
        # 1. 通过API创建任务
        response = client.post("/api/tasks", json={
            "task_name": "时区测试任务",
            "target_id": "target-001",
            "dataset_id": "dataset-001",
            "evaluator_id": "evaluator-001",
            "created_by": "test",
        })
        assert response.status_code == 201
        task_data = response.json()
        assert task_data["code"] == 0
        task = task_data["data"]

        # 2. 验证创建时间
        created_at_str = task["created_at"]
        assert created_at_str is not None, "created_at不应为空"

        # 3. 解析时间并验证是北京时间
        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))

        # 获取当前北京时间（去除时区信息以便比较）
        beijing_now = datetime.now(BEIJING_TZ).replace(tzinfo=None)

        # 验证时间在合理范围内（误差5秒内，考虑API调用延迟）
        created_at_naive = created_at.replace(tzinfo=None)
        diff = abs((created_at_naive - beijing_now).total_seconds())
        assert diff < 5, f"created_at时间与当前北京时间差异超过5秒: created_at={created_at}, 北京时间={beijing_now}"


def test_list_tasks_returns_beijing_time(tmp_path):
    """测试通过API查询任务列表，任务的created_at时间是北京时间"""
    with TestClient(create_app(tmp_path / "task_timezone2.db")) as client:
        # 1. 创建任务
        client.post("/api/tasks", json={
            "task_name": "列表时区测试",
            "target_id": "target-001",
            "dataset_id": "dataset-001",
            "evaluator_id": "evaluator-001",
            "created_by": "test",
        })

        # 2. 查询任务列表
        response = client.get("/api/tasks")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        tasks = data["data"]["content"]
        assert len(tasks) > 0

        # 3. 验证返回的任务时间是北京时间
        task = tasks[0]
        created_at_str = task["created_at"]
        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))

        # 获取北京时间（设置为无时区信息以便比较）
        beijing_now = datetime.now(BEIJING_TZ).replace(tzinfo=None)
        created_at_naive = created_at.replace(tzinfo=None)
        diff = abs((created_at_naive - beijing_now).total_seconds())
        assert diff < 5, f"列表查询的created_at与当前北京时间差异超过5秒: created_at={created_at}, 北京时间={beijing_now}"


def test_task_api_time_format(tmp_path):
    """测试任务API返回的时间格式是ISO 8601格式"""
    with TestClient(create_app(tmp_path / "task_timezone3.db")) as client:
        response = client.post("/api/tasks", json={
            "task_name": "格式测试",
            "target_id": "target-001",
            "dataset_id": "dataset-001",
            "evaluator_id": "evaluator-001",
            "created_by": "test",
        })
        assert response.status_code == 201
        task = response.json()["data"]

        created_at_str = task["created_at"]

        # 验证是ISO 8601格式（包含T）
        assert 'T' in created_at_str, f"时间应该是ISO 8601格式，包含T: {created_at_str}"

        # 验证可以成功解析
        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
        assert created_at is not None
