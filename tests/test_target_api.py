"""L1 契约测试：评测对象注册 API（CRUD、版本化、安全红线、versions() 契约冻结）。

回归锚点：空 DB 下 GET /api/versions 必须返回与改造前完全一致的三条 demo 注册
（15 个旧测试文件依赖此行为，见《02-端到端验证方案》§5）。
"""

import re

import pytest
from fastapi.testclient import TestClient

from agentgate.server.application import create_app

DEMO_IDS = {
    "loan-agent-v1-risky",
    "loan-agent-v2-fixed",
    "langchain-http-agent",
}
VERSIONS_FIELDS = {
    "id", "label", "adapter_type", "endpoint", "credential_ref", "is_latest",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "target-api.db")) as c:
        yield c


def _register(client, **overrides):
    payload = {
        "display_name": "Order Agent",
        "endpoint": "http://127.0.0.1:9000/invoke",
        "description": "订单智能体",
        "capabilities": [
            {"name": "create_order", "kind": "tool", "description": "创建订单"},
        ],
        "timeout_seconds": 15.0,
    }
    payload.update(overrides)
    return client.post("/api/targets", json=payload)


def _register_ok(client, **overrides):
    response = _register(client, **overrides)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert response.json()["code"] == 0
    return data


def test_register_creates_target_with_immutable_v1(client):
    data = _register_ok(client)

    target = data["target"]
    assert target["display_name"] == "Order Agent"
    assert target["external_target_id"] == "order-agent"
    assert target["target_type"] == "agent"
    assert target["adapter_type"] == "http"
    assert target["status"] == "ACTIVE"
    assert target["capabilities"] == [
        {"name": "create_order", "kind": "tool", "description": "创建订单"},
    ]

    version = data["version"]
    assert version["version"] == 1
    assert version["is_latest"] is True
    assert version["endpoint"] == "http://127.0.0.1:9000/invoke"
    assert version["credential_ref"] is None
    assert version["invocation_config"]["timeout_seconds"] == 15.0
    assert SHA256_RE.match(version["content_sha256"])


def test_register_rejects_secret_fields(client):
    for field in ("api_key", "token", "password", "client_secret"):
        response = _register(client, **{field: "sk-super-secret"})
        assert response.status_code == 400, f"{field} 应被拒绝"
        assert "credential_ref" in response.json()["detail"]


def test_register_rejects_invalid_payloads(client):
    assert _register(client, display_name="  ").status_code == 400
    assert _register(client, endpoint="ftp://bad/invoke").status_code == 400
    assert _register(client, endpoint="not-a-url").status_code == 400
    assert _register(client, target_type="workflow").status_code == 400
    assert _register(client, adapter_type="grpc").status_code == 400
    assert _register(
        client, capabilities=[{"kind": "tool"}],
    ).status_code == 400


def test_duplicate_registration_conflicts(client):
    _register_ok(client)
    response = _register(client)
    assert response.status_code == 409


def test_list_detail_and_type_filter(client):
    _register_ok(client)
    _register_ok(client, display_name="Refund Skill", target_type="skill")

    listed = client.get("/api/targets").json()["data"]
    assert len(listed) == 2
    order = next(t for t in listed if t["external_target_id"] == "order-agent")
    assert order["version_count"] == 1
    assert order["latest_version"]["version"] == 1

    skills = client.get("/api/targets", params={"type": "skill"}).json()["data"]
    assert [t["external_target_id"] for t in skills] == ["refund-skill"]

    detail = client.get(f"/api/targets/{order['id']}").json()["data"]
    assert len(detail["versions"]) == 1
    assert detail["versions"][0]["is_latest"] is True

    assert client.get("/api/targets/missing").status_code == 404


def test_publish_version_content_hash_semantics(client):
    data = _register_ok(client)
    target_id = data["target"]["id"]
    v1_sha = data["version"]["content_sha256"]

    # 同配置重发：内容哈希不变
    same = client.post(f"/api/targets/{target_id}/versions", json={})
    assert same.status_code == 201
    v2 = same.json()["data"]
    assert v2["version"] == 2
    assert v2["content_sha256"] == v1_sha
    assert v2["is_latest"] is True

    # 改端点发布：内容哈希变化，is_latest 迁移
    changed = client.post(
        f"/api/targets/{target_id}/versions",
        json={"endpoint": "http://127.0.0.1:9001/invoke"},
    )
    v3 = changed.json()["data"]
    assert v3["version"] == 3
    assert v3["content_sha256"] != v1_sha
    assert v3["is_latest"] is True

    versions = client.get(f"/api/targets/{target_id}").json()["data"]["versions"]
    assert [v["version"] for v in versions] == [3, 2, 1]
    assert sum(v["is_latest"] for v in versions) == 1

    assert client.post(
        "/api/targets/missing/versions", json={},
    ).status_code == 404


def test_published_version_content_is_immutable(client):
    data = _register_ok(client)
    target_id = data["target"]["id"]

    # 端点/认证属于版本内容：PATCH 不允许触碰，只能发布新版本
    response = client.patch(
        f"/api/targets/{target_id}",
        json={"endpoint": "http://127.0.0.1:9999/invoke"},
    )
    assert response.status_code == 400

    # 能力声明是元数据：PATCH 更新不影响已发布版本的快照
    patched = client.patch(
        f"/api/targets/{target_id}",
        json={
            "description": "更新后的描述",
            "capabilities": [{"name": "new_skill", "kind": "tool"}],
        },
    )
    assert patched.status_code == 200
    target = patched.json()["data"]
    assert target["description"] == "更新后的描述"
    assert target["capabilities"] == [
        {"name": "new_skill", "kind": "tool", "description": ""},
    ]
    v1 = client.get(f"/api/targets/{target_id}").json()["data"]["versions"][0]
    assert v1["capabilities"] == [
        {"name": "create_order", "kind": "tool", "description": "创建订单"},
    ]


def test_versions_contract_with_registered_target(client):
    data = _register_ok(client, credential_ref="AGENTGATE_ORDER_KEY")

    versions = client.get("/api/versions").json()
    ids = [item["id"] for item in versions]
    assert DEMO_IDS.issubset(set(ids))
    assert "order-agent-v1" in ids

    entry = next(item for item in versions if item["id"] == "order-agent-v1")
    assert VERSIONS_FIELDS.issubset(entry.keys())
    assert entry["label"] == "Order Agent · v1"
    assert entry["adapter_type"] == "http"
    assert entry["endpoint"] == "http://127.0.0.1:9000/invoke"
    assert entry["credential_ref"] == "AGENTGATE_ORDER_KEY"
    assert entry["is_latest"] is True

    # demo 注册的 latest 语义不被破坏（rerun 默认版本仍指向 demo 修复版本）
    demo_latest = [item for item in versions if item["id"] in DEMO_IDS]
    assert sum(item["is_latest"] for item in demo_latest) == 1
    assert next(
        item["id"] for item in demo_latest if item["is_latest"]
    ) == "loan-agent-v2-fixed"


def test_versions_contract_frozen_on_empty_db(client):
    """空 DB fallback：与改造前完全一致的三条 demo 注册（回归安全网）。"""
    versions = client.get("/api/versions").json()
    assert {item["id"] for item in versions} == DEMO_IDS
    assert all(set(item.keys()) == VERSIONS_FIELDS for item in versions)
    assert sum(item["is_latest"] for item in versions) == 1


def test_soft_delete_and_slug_freeing(client):
    data = _register_ok(client)
    target_id = data["target"]["id"]

    deleted = client.delete(f"/api/targets/{target_id}")
    assert deleted.status_code == 200
    assert deleted.json()["data"] == {"deleted": True, "id": target_id}

    assert client.get(f"/api/targets/{target_id}").status_code == 404
    assert client.get("/api/targets").json()["data"] == []
    assert "order-agent-v1" not in {
        item["id"] for item in client.get("/api/versions").json()
    }

    # external_target_id 已释放：同名对象可以重新注册
    assert _register(client).status_code == 201
    assert client.delete(f"/api/targets/{target_id}").status_code == 404


def test_ad_hoc_test_connection_validates_endpoint(client):
    response = client.post(
        "/api/targets/test-connection",
        json={"endpoint": "not-a-url"},
    )
    assert response.status_code == 400
