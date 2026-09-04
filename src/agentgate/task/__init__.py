"""
Task module for AgentGate evaluation system.

This module handles task scheduling, execution, and management of agent evaluations.
"""

from .domain import (
    TaskStatus,
    AgentType,
    EvaluatorType,
    TargetAgentEntity,
    TargetSnapshot,
    DatasetSnapshot,
    CaseSnapshot,
    CaseTurnSnapshot,
    EvaluatorEntity,
    EvaluatorSnapshot,
    EvalTask,
    TaskRun,
    CaseExecution,
    EvaluationResult,
    TraceInfo,
    EvaluationResultEntity,
)

# 使用统一的 Dataset 和 Case（从 domain.case 导入）
from agentgate.domain.case import Dataset, Case

from .agent import (
    AgentExecutor,
    TargetAgentFactory,
    LocalAgentExecutor,
    SkillAgentExecutor,
    RemoteAgentExecutor,
    WorkflowAgentExecutor,
)

from .evaluator import (
    Evaluator,
    EvaluatorFactory,
    RuleEvaluator,
    LLMJudgeEvaluator,
    CompositeEvaluator,
)

from .service import (
    SchedulerService,
    TaskExecutionService,
    TaskRunner,
)

from .evaluation_center import (
    EvaluationCenterClient,
    get_evaluation_center_client,
    set_evaluation_center_client,
)

__all__ = [
    # Domain
    "TaskStatus",
    "AgentType",
    "EvaluatorType",
    "TargetAgentEntity",
    "TargetSnapshot",
    "Dataset",
    "Case",
    "DatasetSnapshot",
    "CaseSnapshot",
    "CaseTurnSnapshot",
    "EvaluatorEntity",
    "EvaluatorSnapshot",
    "EvalTask",
    "TaskRun",
    "CaseExecution",
    "EvaluationResult",
    "TraceInfo",
    "EvaluationResultEntity",
    # Agent
    "AgentExecutor",
    "TargetAgentFactory",
    "LocalAgentExecutor",
    "SkillAgentExecutor",
    "RemoteAgentExecutor",
    "WorkflowAgentExecutor",
    # Evaluator
    "Evaluator",
    "EvaluatorFactory",
    "RuleEvaluator",
    "LLMJudgeEvaluator",
    "CompositeEvaluator",
    # Service
    "SchedulerService",
    "TaskExecutionService",
    "TaskRunner",
    # Evaluation Center
    "EvaluationCenterClient",
    "get_evaluation_center_client",
    "set_evaluation_center_client",
]
