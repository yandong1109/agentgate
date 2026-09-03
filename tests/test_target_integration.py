"""L2 集成测试：模拟 Agent（FakeHttpAgent）驱动的评测对象全链路。

核心原则（见《02-端到端验证方案》§1）：只 mock 被测对象，不 mock 评测系统——
注册、版本化、连通性测试、评测引擎、trace 关联、结果落库全部走真实组件。
"""

import json

import pytest
from fastapi.testclient import TestClient

from agentgate.server.application import create_app
from tests.fake_http_agent import FakeHttpAgent

SENTINEL_SECRET = "sentinel-secret-123"


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "target-it.db")) as c:
        yield c


@pytest.fixture
def credential_env(monkeypatch):
    monkeypatch.setenv("AGENTGATE_TEST_KEY", SENTINEL_SECRET)
    return "AGENTGATE_TEST_KEY"


def _register(client, endpoint, **overrides):
    payload = {
        "display_name": "Fake Agent",
        "endpoint": endpoint,
        "capabilities": [{"name": "process", "kind": "tool"}],
    }
    payload.update(overrides)
    response = client.post("/api/targets", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _launch(client, version_key):
    response = client.post("/api/evaluations", json={
        "version": version_key,
        "dataset_id": "loan-risk-policy",
        "dataset_version": 1,
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_register_probe_versions_launch_full_pipeline(client):
    """L2-01：注册 → 连通性测试 → 发起评测 → trace 关联 → 结果落库。"""
    with FakeHttpAgent(
        behavior="success", repository=client.app.state.repository,
    ) as agent:
        data = _register(client, agent.endpoint)
        target_id = data["target"]["id"]

        probe = client.post(f"/api/targets/{target_id}/test-connection", json={})
        assert probe.status_code == 200
        assert probe.json()["data"]["ok"] is True

        ids = {item["id"] for item in client.get("/api/versions").json()}
        assert "fake-agent-v1" in ids

        launched = _launch(client, "fake-agent-v1")
        assert launched["status"] == "completed"
        run_id = launched["id"]

        case_ids = [
            case["id"] for case in launched["snapshot"]["dataset"]["cases"]
        ]
        for case_id in case_ids:
            trace = client.get(f"/api/runs/{run_id}/traces/{case_id}")
            assert trace.status_code == 200
            assert trace.json()["status"] == "complete"

        results = client.get(f"/api/runs/{run_id}").json()
        assert results["gate"] is not None


def test_authorization_header_injected_from_credential_ref(client, credential_env):
    """L2-02：credential_ref 经环境变量解析后注入 Authorization 头。"""
    with FakeHttpAgent(behavior="success") as agent:
        data = _register(client, agent.endpoint, credential_ref=credential_env)
        response = client.post(
            f"/api/targets/{data['target']['id']}/test-connection", json={},
        )
        assert response.json()["data"]["ok"] is True
        headers = agent.received_headers[-1]
        assert headers["authorization"] == SENTINEL_SECRET


def test_missing_credential_env_reports_unauthorized(client):
    """凭证环境变量未配置时，探测返回 unauthorized 且不泄漏任何密钥。"""
    with FakeHttpAgent(behavior="success") as agent:
        data = _register(
            client, agent.endpoint, credential_ref="AGENTGATE_UNSET_KEY_XYZ",
        )
        result = client.post(
            f"/api/targets/{data['target']['id']}/test-connection", json={},
        ).json()["data"]
        assert result["ok"] is False
        assert result["error_code"] == "unauthorized"
        assert "AGENTGATE_UNSET_KEY_XYZ" in result["message"]
        # 未发任何请求
        assert agent.received_headers == []


def test_correlation_headers_reach_agent_on_launch(client):
    """L2-03：关联头（Run/Case ID）随评测执行传播到被测 Agent。"""
    with FakeHttpAgent(
        behavior="success", repository=client.app.state.repository,
    ) as agent:
        _register(client, agent.endpoint)
        launched = _launch(client, "fake-agent-v1")
        run_id = launched["id"]
        case_ids = {case["id"] for case in launched["snapshot"]["dataset"]["cases"]}

        seen_runs, seen_cases = set(), set()
        for headers in agent.received_headers:
            if headers.get("x-agentgate-run-id") == run_id:
                seen_runs.add(headers["x-agentgate-run-id"])
                seen_cases.add(headers["x-agentgate-case-id"])
        assert seen_runs == {run_id}
        assert seen_cases == case_ids


@pytest.mark.parametrize(("behavior", "expected_code"), [
    ("401", "unauthorized"),
    ("500", "unavailable"),
    ("bad_content_type", "protocol_error"),
    ("missing_fields", "protocol_error"),
])
def test_error_classification_matrix(client, behavior, expected_code):
    """L2-05：被测 Agent 异常行为 → TargetIntegrationError 分类映射。"""
    with FakeHttpAgent(behavior=behavior) as agent:
        result = client.post("/api/targets/test-connection", json={
            "endpoint": agent.endpoint,
            "timeout_seconds": 5.0,
        }).json()["data"]
        assert result["ok"] is False
        assert result["error_code"] == expected_code


def test_dead_endpoint_maps_to_timeout(client):
    """端口不通：适配器现有行为将 URLError 归类为 timeout。"""
    result = client.post("/api/targets/test-connection", json={
        "endpoint": "http://127.0.0.1:1/invoke",
        "timeout_seconds": 2.0,
    }).json()["data"]
    assert result["ok"] is False
    assert result["error_code"] == "timeout"


def test_timeout_and_secret_redaction(client):
    """L2-04：超时受控；错误响应不得回显密钥明文（脱敏防线）。"""
    with FakeHttpAgent(behavior="slow") as agent:
        endpoint = f"{agent.endpoint}?api_key={SENTINEL_SECRET}"
        response = client.post("/api/targets/test-connection", json={
            "endpoint": endpoint,
            "timeout_seconds": 1.0,
        })
        result = response.json()["data"]
        assert result["ok"] is False
        assert result["error_code"] == "timeout"
        assert result["latency_ms"] < 5000
        assert SENTINEL_SECRET not in json.dumps(response.json())


def test_snapshot_immutable_across_versions(client):
    """L2-06（REQ-002）：发布 v2 后，历史 run 固化的 v1 快照不变。"""
    with FakeHttpAgent(
        behavior="success", repository=client.app.state.repository,
    ) as agent:
        data = _register(client, agent.endpoint)
        target_id = data["target"]["id"]
        launched = _launch(client, "fake-agent-v1")
        run_id = launched["id"]
        target_before = launched["snapshot"]["target"]
        assert target_before["ref"]["external_version_id"] == "fake-agent-v1"

        v2 = client.post(
            f"/api/targets/{target_id}/versions",
            json={"timeout_seconds": 20.0},
        )
        assert v2.status_code == 201
        assert v2.json()["data"]["is_latest"] is True

        runs = client.get("/api/runs").json()
        stored = next(run for run in runs if run["id"] == run_id)
        target_after = stored["snapshot"]["target"]
        assert target_after["ref"]["external_version_id"] == "fake-agent-v1"
        assert target_after["content_sha256"] == target_before["content_sha256"]


def test_delete_blocked_by_run_reference(client):
    """被运行记录引用的评测对象不可删除（保住历史 run 可解释性）。"""
    with FakeHttpAgent(
        behavior="success", repository=client.app.state.repository,
    ) as agent:
        data = _register(client, agent.endpoint)
        target_id = data["target"]["id"]
        _launch(client, "fake-agent-v1")

        response = client.delete(f"/api/targets/{target_id}")
        assert response.status_code == 409


def test_get_target_info_shape_for_task_module(client, credential_env):
    """L2-07：task 模块 _get_target_info 的数据源契约（S3 接线）。"""
    with FakeHttpAgent(behavior="success") as agent:
        _register(client, agent.endpoint, credential_ref=credential_env)
        service = client.app.state.target_service

        info = service.get_target_info("fake-agent-v1")
        assert info == {
            "agent_name": "Fake Agent",
            "agent_type": "REMOTE_AGENT",
            "config": {
                "endpoint": agent.endpoint,
                "credential_ref": credential_env,
            },
            "status": "ACTIVE",
        }

        fallback = service.get_target_info("unknown-target")
        assert fallback == {
            "agent_name": "unknown-target",
            "agent_type": "REMOTE_AGENT",
            "config": {},
            "status": "ACTIVE",
        }


def test_task_module_get_target_info_bridge(client, credential_env):
    """S3：task/api.py::_get_target_info 切换到 target 服务数据源。"""
    with FakeHttpAgent(behavior="success") as agent:
        _register(client, agent.endpoint, credential_ref=credential_env)

        from agentgate.task.api import _get_target_info

        info = _get_target_info("fake-agent-v1")
        assert info["agent_name"] == "Fake Agent"
        assert info["agent_type"] == "REMOTE_AGENT"
        assert info["config"]["endpoint"] == agent.endpoint
        assert info["config"]["credential_ref"] == credential_env

        # 未知 id（如 demo 注册）：与旧行为一致的回退结构
        fallback = _get_target_info("loan-agent-v2-fixed")
        assert fallback == {
            "agent_name": "loan-agent-v2-fixed",
            "agent_type": "REMOTE_AGENT",
            "config": {},
            "status": "ACTIVE",
        }
