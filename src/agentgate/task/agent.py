"""
智能体执行器模块。

提供 AgentExecutor 抽象基类和具体的智能体执行器实现。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .domain import AgentType, TraceInfo

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AgentExecutor(ABC):
    """智能体执行时的公共抽象父类"""

    @abstractmethod
    def initialize(self) -> None:
        """初始化方法，用于创建agent链接等初始化工作"""
        pass

    @abstractmethod
    def send_query(self, question: str) -> str:
        """
        发送查询请求方法，调用agent接口查询结果
        :param question: 要查询的问题
        :return: 查询结果
        """
        pass

    @abstractmethod
    def get_trace(self) -> TraceInfo:
        """
        获取agent处理的trace详细信息
        :return: trace详情
        """
        pass

    def close(self) -> None:
        """关闭智能体连接"""
        pass


class LocalAgentExecutor(AgentExecutor):
    """本地测试执行器，用于测试环境"""

    def __init__(self, config: dict):
        self.config = config
        self.initialized = False
        self.query_count = 0

    def initialize(self) -> None:
        self.initialized = True
        logger.info(f"LocalAgentExecutor initialized with config: {self.config}")

    def send_query(self, question: str) -> str:
        self.query_count += 1
        return f"[Local Test Response] Received: {question}"

    def get_trace(self) -> TraceInfo:
        return TraceInfo(
            session_id=f"local-session-{self.query_count}",
            rounds=[{"round": 1, "user_input": "test", "agent_response": "test response"}],
            tool_calls=[],
            total_duration_ms=100
        )

    def close(self) -> None:
        self.initialized = False


class SkillAgentExecutor(AgentExecutor):
    """技能型智能体执行器"""

    def __init__(self, config: dict):
        self.config = config
        self.initialized = False
        self.query_count = 0
        self._skill_name = config.get("skill_name", "")

    def initialize(self) -> None:
        self.initialized = True
        logger.info(f"SkillAgentExecutor initialized with skill: {self._skill_name}")

    def send_query(self, question: str) -> str:
        self.query_count += 1
        return f"[Skill Response] {self._skill_name}: {question}"

    def get_trace(self) -> TraceInfo:
        return TraceInfo(
            session_id=f"skill-session-{self.query_count}",
            rounds=[{"round": 1, "user_input": "test", "agent_response": "skill response"}],
            tool_calls=[{"tool": "skill_call", "input": self._skill_name}],
            total_duration_ms=50
        )

    def close(self) -> None:
        self.initialized = False


class RemoteAgentExecutor(AgentExecutor):
    """远端Agent执行器"""

    def __init__(self, config: dict):
        self.config = config
        self.initialized = False
        self.query_count = 0
        self._remote_url = config.get("remote_url", "")
        self._api_key = config.get("api_key", "")

    def initialize(self) -> None:
        self.initialized = True
        logger.info(f"RemoteAgentExecutor initialized with url: {self._remote_url}")

    def send_query(self, question: str) -> str:
        self.query_count += 1
        return f"[Remote Response] {question}"

    def get_trace(self) -> TraceInfo:
        return TraceInfo(
            session_id=f"remote-session-{self.query_count}",
            rounds=[{"round": 1, "user_input": "test", "agent_response": "remote response"}],
            tool_calls=[{"tool": "remote_call", "url": self._remote_url}],
            total_duration_ms=200
        )

    def close(self) -> None:
        self.initialized = False


class WorkflowAgentExecutor(AgentExecutor):
    """Agent工作流执行器"""

    def __init__(self, config: dict):
        self.config = config
        self.initialized = False
        self.query_count = 0
        self._workflow_id = config.get("workflow_id", "")

    def initialize(self) -> None:
        self.initialized = True
        logger.info(f"WorkflowAgentExecutor initialized with workflow: {self._workflow_id}")

    def send_query(self, question: str) -> str:
        self.query_count += 1
        return f"[Workflow Response] {self._workflow_id}: {question}"

    def get_trace(self) -> TraceInfo:
        return TraceInfo(
            session_id=f"workflow-session-{self.query_count}",
            rounds=[{"round": 1, "user_input": "test", "agent_response": "workflow response"}],
            tool_calls=[{"tool": "workflow_call", "workflow_id": self._workflow_id}],
            total_duration_ms=300
        )

    def close(self) -> None:
        self.initialized = False


class TargetAgentFactory:
    """智能体工厂类，根据类型和配置创建智能体实例"""

    @staticmethod
    def create(agent_type: str | AgentType, config: dict) -> AgentExecutor:
        """
        创建智能体实例
        :param agent_type: 智能体类型（SKILL/REMOTE_AGENT/AGENT_WORKFLOW）
        :param config: 智能体属性配置
        :return: AgentExecutor实例
        """
        if isinstance(agent_type, str):
            agent_type = AgentType(agent_type)

        executors = {
            AgentType.SKILL: SkillAgentExecutor,
            AgentType.REMOTE_AGENT: RemoteAgentExecutor,
            AgentType.AGENT_WORKFLOW: WorkflowAgentExecutor,
        }

        executor_class = executors.get(agent_type)
        if not executor_class:
            raise ValueError(f"Unknown agent type: {agent_type}")

        return executor_class(config)
