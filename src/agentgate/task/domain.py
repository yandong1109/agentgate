"""
Domain models for the Task scheduling module.

This module defines the core domain entities for task scheduling,
including Task, TaskRun, TargetAgent, Dataset, Case, and Evaluator.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import StrEnum
from typing import Any

# 北京时区 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))


def utcnow() -> datetime:
    """返回当前北京时间"""
    return datetime.now(BEIJING_TZ)


def generate_uuid() -> str:
    """生成UUID字符串"""
    return str(uuid.uuid4())


# ============================================================================
# 枚举定义
# ============================================================================


class TaskStatus(StrEnum):
    """任务状态枚举"""
    NEW = "NEW"                    # 新建
    PENDING = "PENDING"            # 待执行
    RUNNING = "RUNNING"            # 执行中
    SUCCESS = "SUCCESS"            # 执行成功
    FAIL = "FAIL"                  # 执行失败
    TERMINATED = "TERMINATED"      # 人工终止


class AgentType(StrEnum):
    """智能体类型枚举"""
    SKILL = "SKILL"                        # 技能型智能体
    REMOTE_AGENT = "REMOTE_AGENT"          # 远端Agent
    AGENT_WORKFLOW = "AGENT_WORKFLOW"      # Agent工作流


class EvaluatorType(StrEnum):
    """评估器类型枚举"""
    RULE = "RULE"                  # 规则评估器
    LLM = "LLM"                    # LLM评估器
    COMPOSITE = "COMPOSITE"        # 复合评估器


# ============================================================================
# 数据类定义
# ============================================================================


@dataclass
class TraceInfo:
    """智能体执行trace信息"""
    session_id: str
    rounds: list[dict] = field(default_factory=list)       # 多轮对话
    tool_calls: list[dict] = field(default_factory=list)   # 工具调用
    total_duration_ms: int = 0                               # 总耗时


@dataclass
class EvaluationResult:
    """评估结果"""
    score: float = 0.0
    passed: bool = False
    reasons: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)


# ============================================================================
# 实体定义（用于API响应和数据传输）
# ============================================================================


@dataclass
class TargetAgentEntity:
    """智能体实体"""
    id: str = field(default_factory=generate_uuid)
    agent_name: str = ""
    agent_type: AgentType = AgentType.REMOTE_AGENT
    config: dict = field(default_factory=dict)
    status: str = "ACTIVE"
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "agent_type": self.agent_type.value if isinstance(self.agent_type, StrEnum) else self.agent_type,
            "config": self.config,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class TargetSnapshot:
    """评测对象快照"""
    id: str = field(default_factory=generate_uuid)
    target_id: str = ""                          # 原对象ID
    agent_name: str = ""                         # 评测对象名称（原对象业务字段）
    agent_type: str = ""                         # 评测对象类型（原对象业务字段）
    config: dict = field(default_factory=dict)   # 配置信息（原对象业务字段）
    status: str = "ACTIVE"                       # 状态（原对象业务字段）
    created_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "target_id": self.target_id,
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "config": self.config,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class DatasetSnapshot:
    """测评集快照 - 与 domain.case.Dataset 字段对应"""
    id: str = field(default_factory=generate_uuid)
    dataset_id: str = ""                          # 原对象ID
    name: str = ""                                # 名称（原对象业务字段）
    description: str = ""                         # 描述（原对象业务字段）
    purpose: str = "standard"                     # 用途（原对象业务字段）
    archived: bool = False                        # 是否归档（原对象业务字段）
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "dataset_id": self.dataset_id,
            "name": self.name,
            "description": self.description,
            "purpose": self.purpose,
            "archived": self.archived,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class CaseSnapshot:
    """用例快照 - 与 domain.case.Case 字段对应"""
    id: str = field(default_factory=generate_uuid)
    case_id: str = ""                             # 原对象ID
    name: str = ""                                # 名称（原对象业务字段）
    initial_state: dict = field(default_factory=dict)  # 初始状态（原对象业务字段）
    category: str = "positive"                    # 类别（原对象业务字段）
    difficulty: str = "medium"                    # 难度（原对象业务字段）
    tags: str = ""                                # 标签（原对象业务字段）
    notes: str = ""                               # 备注（原对象业务字段）
    created_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "case_id": self.case_id,
            "name": self.name,
            "initial_state": self.initial_state,
            "category": self.category,
            "difficulty": self.difficulty,
            "tags": self.tags,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class CaseTurnSnapshot:
    """用例轮次快照 - 与 domain.case.CaseTurn 字段对应"""
    id: str = field(default_factory=generate_uuid)
    case_snapshot_id: str = ""                    # 关联的CaseSnapshot ID
    case_turn_id: str = ""                        # 原对象ID
    input: dict = field(default_factory=dict)     # 输入（原对象业务字段）
    expected_skill: str = ""                      # 期望技能（原对象业务字段）
    expectations: str = ""                        # 期望值JSON（原对象业务字段）
    required_tools: str = ""                      # 必需工具JSON（原对象业务字段）
    forbidden_tools: str = ""                     # 禁用工具JSON（原对象业务字段）
    policy_rules: str = ""                        # 策略规则JSON（原对象业务字段）
    notes: str = ""                               # 备注（原对象业务字段）
    created_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "case_snapshot_id": self.case_snapshot_id,
            "case_turn_id": self.case_turn_id,
            "input": self.input,
            "expected_skill": self.expected_skill,
            "expectations": self.expectations,
            "required_tools": self.required_tools,
            "forbidden_tools": self.forbidden_tools,
            "policy_rules": self.policy_rules,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class EvaluatorEntity:
    """评估器实体"""
    id: str = field(default_factory=generate_uuid)
    name: str = ""
    evaluator_type: EvaluatorType = EvaluatorType.RULE
    config: dict = field(default_factory=dict)
    status: str = "ACTIVE"
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "evaluator_type": self.evaluator_type.value if isinstance(self.evaluator_type, StrEnum) else self.evaluator_type,
            "config": self.config,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class EvaluatorSnapshot:
    """评估器快照"""
    id: str = field(default_factory=generate_uuid)
    evaluator_id: str = ""
    evaluator_type: str = ""
    snapshot_data: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "evaluator_id": self.evaluator_id,
            "evaluator_type": self.evaluator_type,
            "snapshot_data": self.snapshot_data,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class EvalTask:
    """评测任务实体"""
    id: str = field(default_factory=generate_uuid)
    task_name: str = ""
    target_id: str = ""
    dataset_id: str = ""
    evaluator_id: str = ""
    status: TaskStatus = TaskStatus.NEW
    created_by: str = ""
    # 快照ID（在启动任务时创建）
    target_snapshot_id: str = ""
    dataset_snapshot_id: str = ""
    evaluator_snapshot_id: str = ""
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    # 关联对象（可选，用于API响应）
    target: TargetAgentEntity | None = None
    dataset: Dataset | None = None
    evaluator: EvaluatorEntity | None = None
    latest_run: TaskRun | None = None

    def to_dict(self) -> dict:
        result = {
            "id": self.id,
            "task_name": self.task_name,
            "target_id": self.target_id,
            "dataset_id": self.dataset_id,
            "evaluator_id": self.evaluator_id,
            "status": self.status.value if isinstance(self.status, StrEnum) else self.status,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            # 快照ID
            "target_snapshot_id": self.target_snapshot_id,
            "dataset_snapshot_id": self.dataset_snapshot_id,
            "evaluator_snapshot_id": self.evaluator_snapshot_id,
        }

        # 添加关联对象信息
        if self.target:
            result["target_name"] = self.target.agent_name
            result["target_type"] = self.target.agent_type.value if isinstance(self.target.agent_type, StrEnum) else self.target.agent_type
        if self.dataset:
            result["dataset_name"] = self.dataset.name
        if self.evaluator:
            result["evaluator_name"] = self.evaluator.name
        if self.latest_run:
            result["latest_run"] = self.latest_run.to_dict()

        return result


@dataclass
class TaskRun:
    """任务执行记录实体"""
    id: str = field(default_factory=generate_uuid)
    task_id: str = ""
    run_no: int = 0
    status: TaskStatus = TaskStatus.NEW
    target_snapshot_id: str = ""
    dataset_snapshot_id: str = ""
    evaluator_snapshot_id: str = ""
    total_cases: int = 0
    completed_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    avg_score: float = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    terminated_by: str = ""
    error_message: str = ""
    created_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "run_no": self.run_no,
            "status": self.status.value if isinstance(self.status, StrEnum) else self.status,
            "target_snapshot_id": self.target_snapshot_id,
            "dataset_snapshot_id": self.dataset_snapshot_id,
            "evaluator_snapshot_id": self.evaluator_snapshot_id,
            "total_cases": self.total_cases,
            "completed_cases": self.completed_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "avg_score": self.avg_score,
            "pass_rate": round(self.passed_cases / self.total_cases * 100, 1) if self.total_cases > 0 else 0,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "terminated_by": self.terminated_by,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class CaseExecution:
    """用例执行记录实体"""
    id: str = field(default_factory=generate_uuid)
    run_id: str = ""
    case_id: str = ""
    status: TaskStatus = TaskStatus.PENDING
    score: float = 0.0
    passed: bool = False
    agent_response: str = ""
    trace_data: dict = field(default_factory=dict)
    evaluation_result_id: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "status": self.status.value if isinstance(self.status, StrEnum) else self.status,
            "score": self.score,
            "passed": self.passed,
            "agent_response": self.agent_response,
            "trace_data": self.trace_data,
            "evaluation_result_id": self.evaluation_result_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class EvaluationResultEntity:
    """评估结果实体"""
    id: str = field(default_factory=generate_uuid)
    case_execution_id: str = ""
    evaluator_id: str = ""
    score: float = 0.0
    passed: bool = False
    details: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "case_execution_id": self.case_execution_id,
            "evaluator_id": self.evaluator_id,
            "score": self.score,
            "passed": self.passed,
            "details": self.details,
            "created_at": self.created_at.isoformat(),
        }
