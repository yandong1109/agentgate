"""
Agent executor tests.
"""

import pytest
from agentgate.task.agent import (
    AgentExecutor,
    LocalAgentExecutor,
    RemoteAgentExecutor,
    SkillAgentExecutor,
    TargetAgentFactory,
    WorkflowAgentExecutor,
)
from agentgate.task.domain import AgentType


def test_local_agent_executor():
    """测试本地测试执行器"""
    executor = LocalAgentExecutor({"mode": "test"})
    executor.initialize()
    assert executor.initialized is True

    response = executor.send_query("Hello")
    assert "Hello" in response

    trace = executor.get_trace()
    assert trace.session_id.startswith("local-session")

    executor.close()
    assert executor.initialized is False


def test_skill_agent_executor():
    """测试技能型智能体执行器"""
    executor = SkillAgentExecutor({"skill_name": "test_skill"})
    executor.initialize()
    assert executor.initialized is True

    response = executor.send_query("Hello")
    assert "test_skill" in response

    trace = executor.get_trace()
    assert trace.session_id.startswith("skill-session")

    executor.close()


def test_remote_agent_executor():
    """测试远端Agent执行器"""
    executor = RemoteAgentExecutor({
        "remote_url": "https://api.example.com/agent",
        "api_key": "test-key",
    })
    executor.initialize()
    assert executor.initialized is True

    response = executor.send_query("Hello")
    assert "Remote Response" in response

    trace = executor.get_trace()
    assert trace.session_id.startswith("remote-session")

    executor.close()


def test_workflow_agent_executor():
    """测试工作流Agent执行器"""
    executor = WorkflowAgentExecutor({"workflow_id": "wf-123"})
    executor.initialize()
    assert executor.initialized is True

    response = executor.send_query("Hello")
    assert "wf-123" in response

    trace = executor.get_trace()
    assert trace.session_id.startswith("workflow-session")

    executor.close()


def test_target_agent_factory_skill():
    """测试工厂创建技能型智能体"""
    executor = TargetAgentFactory.create(
        AgentType.SKILL,
        {"skill_name": "test_skill"}
    )
    assert isinstance(executor, SkillAgentExecutor)


def test_target_agent_factory_remote_agent():
    """测试工厂创建远端Agent"""
    executor = TargetAgentFactory.create(
        AgentType.REMOTE_AGENT,
        {"remote_url": "https://api.example.com"}
    )
    assert isinstance(executor, RemoteAgentExecutor)


def test_target_agent_factory_workflow():
    """测试工厂创建工作流Agent"""
    executor = TargetAgentFactory.create(
        AgentType.AGENT_WORKFLOW,
        {"workflow_id": "wf-123"}
    )
    assert isinstance(executor, WorkflowAgentExecutor)


def test_target_agent_factory_string_type():
    """测试工厂创建（字符串类型）"""
    executor = TargetAgentFactory.create(
        "SKILL",
        {"skill_name": "test_skill"}
    )
    assert isinstance(executor, SkillAgentExecutor)


def test_target_agent_factory_unknown_type():
    """测试工厂创建（未知类型）"""
    with pytest.raises(ValueError):
        TargetAgentFactory.create("UNKNOWN", {})
