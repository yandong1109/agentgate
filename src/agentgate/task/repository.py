"""
任务模块持久化层。

提供SQLAlchemy模型和仓储实现。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer,
    JSON, String, Text, create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker

from .domain import AgentType, EvaluatorType, TaskStatus

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

Base = declarative_base()


class TargetAgentModel(Base):
    """智能体表模型"""
    __tablename__ = "target_agent"

    id = Column(String(36), primary_key=True)
    agent_name = Column(String(255), nullable=False)
    agent_type = Column(String(32), nullable=False)
    config = Column(JSON, default=dict)
    status = Column(String(32), default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TargetSnapshotModel(Base):
    """评测对象快照表模型"""
    __tablename__ = "target_snapshot"

    id = Column(String(36), primary_key=True)
    target_id = Column(String(36), ForeignKey("target_agent.id"))
    agent_name = Column(String(255), default="")
    agent_type = Column(String(32), default="")
    config = Column(JSON, default=dict)
    status = Column(String(32), default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow)


class DatasetModel(Base):
    """测评集表模型"""
    __tablename__ = "dataset"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(32), default="ACTIVE")
    created_by = Column(String(128))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CaseModel(Base):
    """测试用例表模型"""
    __tablename__ = "case_table"

    id = Column(String(36), primary_key=True)
    dataset_id = Column(String(36), ForeignKey("dataset.id"))
    name = Column(String(255))
    case_data = Column(JSON, default=dict)
    tags = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)


class DatasetSnapshotModel(Base):
    """测评集快照表模型"""
    __tablename__ = "dataset_snapshot"

    id = Column(String(36), primary_key=True)
    dataset_id = Column(String(36), ForeignKey("dataset.id"))
    name = Column(String(255), default="")
    description = Column(Text, default="")
    purpose = Column(String(32), default="standard")
    archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class CaseSnapshotModel(Base):
    """用例快照表模型"""
    __tablename__ = "case_snapshot"

    id = Column(String(36), primary_key=True)
    case_id = Column(String(36), ForeignKey("case_table.id"))
    name = Column(String(255), default="")
    initial_state = Column(JSON, default=dict)
    category = Column(String(32), default="positive")
    difficulty = Column(String(32), default="medium")
    tags = Column(String(255), default="")
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class CaseTurnSnapshotModel(Base):
    """用例轮次快照表模型"""
    __tablename__ = "case_turn_snapshot"

    id = Column(String(36), primary_key=True)
    case_snapshot_id = Column(String(36), ForeignKey("case_snapshot.id"))
    case_turn_id = Column(String(36), default="")
    input = Column(JSON, default=dict)
    expected_skill = Column(String(255), default="")
    expectations = Column(Text, default="")
    required_tools = Column(Text, default="")
    forbidden_tools = Column(Text, default="")
    policy_rules = Column(Text, default="")
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class EvaluatorModel(Base):
    """评估器表模型"""
    __tablename__ = "evaluator"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    evaluator_type = Column(String(32), nullable=False)
    config = Column(JSON, default=dict)
    status = Column(String(32), default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EvaluatorSnapshotModel(Base):
    """评估器快照表模型"""
    __tablename__ = "evaluator_snapshot"

    id = Column(String(36), primary_key=True)
    evaluator_id = Column(String(36), ForeignKey("evaluator.id"))
    evaluator_type = Column(String(32))
    snapshot_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class EvalTaskModel(Base):
    """评测任务表模型"""
    __tablename__ = "eval_task"

    id = Column(String(36), primary_key=True)
    task_name = Column(String(255), nullable=False)
    target_id = Column(String(36), ForeignKey("target_agent.id"))
    dataset_id = Column(String(36), ForeignKey("dataset.id"))
    evaluator_id = Column(String(36), ForeignKey("evaluator.id"))
    status = Column(String(32), default="NEW")
    created_by = Column(String(128))
    # 快照ID（在启动任务时创建）
    target_snapshot_id = Column(String(36))
    dataset_snapshot_id = Column(String(36))
    evaluator_snapshot_id = Column(String(36))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TaskRunModel(Base):
    """任务执行记录表模型"""
    __tablename__ = "task_run"

    id = Column(String(36), primary_key=True)
    task_id = Column(String(36), ForeignKey("eval_task.id"))
    run_no = Column(Integer, default=0)
    status = Column(String(32), default="NEW")
    target_snapshot_id = Column(String(36), ForeignKey("target_snapshot.id"))
    dataset_snapshot_id = Column(String(36), ForeignKey("dataset_snapshot.id"))
    evaluator_snapshot_id = Column(String(36), ForeignKey("evaluator_snapshot.id"))
    total_cases = Column(Integer, default=0)
    completed_cases = Column(Integer, default=0)
    passed_cases = Column(Integer, default=0)
    failed_cases = Column(Integer, default=0)
    avg_score = Column(Float, default=0.0)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    terminated_by = Column(String(128))
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class CaseExecutionModel(Base):
    """用例执行记录表模型"""
    __tablename__ = "case_execution"

    id = Column(String(36), primary_key=True)
    run_id = Column(String(36), ForeignKey("task_run.id"))
    case_id = Column(String(36), ForeignKey("case_table.id"))
    status = Column(String(32), default="PENDING")
    score = Column(Float, default=0.0)
    passed = Column(Boolean, default=False)
    agent_response = Column(Text)
    trace_data = Column(JSON, default=dict)
    evaluation_result_id = Column(String(36), ForeignKey("evaluation_result.id"))
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class EvaluationResultModel(Base):
    """评估结果表模型"""
    __tablename__ = "evaluation_result"

    id = Column(String(36), primary_key=True)
    case_execution_id = Column(String(36), ForeignKey("case_execution.id"))
    evaluator_id = Column(String(36), ForeignKey("evaluator.id"))
    score = Column(Float, default=0.0)
    passed = Column(Boolean, default=False)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class TaskRepository:
    """任务仓储"""

    def __init__(self, session: Session):
        self.session = session

    def create_task(self, task: "EvalTask") -> EvalTask:
        """创建任务"""
        model = EvalTaskModel(
            id=task.id,
            task_name=task.task_name,
            target_id=task.target_id,
            dataset_id=task.dataset_id,
            evaluator_id=task.evaluator_id,
            status=task.status.value if hasattr(task.status, "value") else task.status,
            created_by=task.created_by,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
        self.session.add(model)
        self.session.commit()
        return task

    def get_task(self, task_id: str) -> EvalTask | None:
        """获取任务"""
        model = self.session.query(EvalTaskModel).filter(EvalTaskModel.id == task_id).first()
        if not model:
            return None
        return self._to_task_entity(model)

    def list_tasks(
        self,
        status: str | None = None,
        target_id: str | None = None,
        page: int = 0,
        size: int = 10,
    ) -> list[EvalTask]:
        """查询任务列表（按创建时间倒序）"""
        query = self.session.query(EvalTaskModel)

        if status:
            query = query.filter(EvalTaskModel.status == status)
        if target_id:
            query = query.filter(EvalTaskModel.target_id == target_id)

        # 按创建时间倒序排列
        query = query.order_by(EvalTaskModel.created_at.desc())
        query = query.offset(page * size).limit(size)
        models = query.all()

        return [self._to_task_entity(m) for m in models]

    def count_tasks(
        self,
        status: str | None = None,
        target_id: str | None = None,
    ) -> int:
        """统计任务数量"""
        query = self.session.query(EvalTaskModel)

        if status:
            query = query.filter(EvalTaskModel.status == status)
        if target_id:
            query = query.filter(EvalTaskModel.target_id == target_id)

        return query.count()

    def update_task(self, task: EvalTask) -> EvalTask:
        """更新任务"""
        from .domain import utcnow
        model = self.session.query(EvalTaskModel).filter(EvalTaskModel.id == task.id).first()
        if model:
            model.status = task.status.value if hasattr(task.status, "value") else task.status
            # 更新快照ID字段（如果任务有这些属性）
            if hasattr(task, 'target_snapshot_id') and task.target_snapshot_id:
                model.target_snapshot_id = task.target_snapshot_id
            if hasattr(task, 'dataset_snapshot_id') and task.dataset_snapshot_id:
                model.dataset_snapshot_id = task.dataset_snapshot_id
            if hasattr(task, 'evaluator_snapshot_id') and task.evaluator_snapshot_id:
                model.evaluator_snapshot_id = task.evaluator_snapshot_id
            model.updated_at = utcnow()
            self.session.commit()
        return task

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        model = self.session.query(EvalTaskModel).filter(EvalTaskModel.id == task_id).first()
        if model:
            self.session.delete(model)
            self.session.commit()
            return True
        return False

    def create_run(self, run: TaskRun) -> TaskRun:
        """创建执行记录"""
        model = TaskRunModel(
            id=run.id,
            task_id=run.task_id,
            run_no=run.run_no,
            status=run.status.value if hasattr(run.status, "value") else run.status,
            target_snapshot_id=run.target_snapshot_id,
            dataset_snapshot_id=run.dataset_snapshot_id,
            evaluator_snapshot_id=run.evaluator_snapshot_id,
            total_cases=run.total_cases,
            completed_cases=run.completed_cases,
            passed_cases=run.passed_cases,
            failed_cases=run.failed_cases,
            avg_score=run.avg_score,
            created_at=run.created_at,
        )
        self.session.add(model)
        self.session.commit()
        return run

    def update_run(self, run: TaskRun) -> TaskRun:
        """更新执行记录"""
        model = self.session.query(TaskRunModel).filter(TaskRunModel.id == run.id).first()
        if model:
            model.status = run.status.value if hasattr(run.status, "value") else run.status
            model.completed_cases = run.completed_cases
            model.passed_cases = run.passed_cases
            model.failed_cases = run.failed_cases
            model.avg_score = run.avg_score
            model.started_at = run.started_at
            model.completed_at = run.completed_at
            model.terminated_by = run.terminated_by
            model.error_message = run.error_message
            self.session.commit()
        return run

    def create_case_execution(self, execution: "CaseExecution") -> "CaseExecution":
        """创建用例执行记录"""
        model = CaseExecutionModel(
            id=execution.id,
            run_id=execution.run_id,
            case_id=execution.case_id,
            status=execution.status.value if hasattr(execution.status, "value") else execution.status,
            score=execution.score,
            passed=execution.passed,
            agent_response=execution.agent_response,
            trace_data=execution.trace_data,
            evaluation_result_id=execution.evaluation_result_id,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            created_at=execution.created_at,
        )
        self.session.add(model)
        self.session.commit()
        return execution

    def get_run(self, run_id: str) -> TaskRun | None:
        """获取执行记录"""
        model = self.session.query(TaskRunModel).filter(TaskRunModel.id == run_id).first()
        if not model:
            return None
        return self._to_run_entity(model)

    def list_runs(self, task_id: str) -> list[TaskRun]:
        """查询执行记录列表"""
        models = self.session.query(TaskRunModel).filter(TaskRunModel.task_id == task_id).all()
        return [self._to_run_entity(m) for m in models]

    def count_cases_by_dataset(self, dataset_id: str) -> int:
        """统计测评集下的用例数量"""
        return self.session.query(CaseModel).filter(CaseModel.dataset_id == dataset_id).count()

    def list_cases_by_dataset(self, dataset_id: str) -> list[dict]:
        """查询测评集下的所有用例"""
        models = self.session.query(CaseModel).filter(CaseModel.dataset_id == dataset_id).all()
        return [self._to_case_dict(m) for m in models]

    def list_case_executions(self, run_id: str) -> list[dict]:
        """查询用例执行记录列表"""
        models = self.session.query(CaseExecutionModel).filter(CaseExecutionModel.run_id == run_id).all()
        return [self._to_case_execution_dict(m) for m in models]

    def get_case(self, case_id: str) -> dict | None:
        """获取用例详情"""
        model = self.session.query(CaseModel).filter(CaseModel.id == case_id).first()
        if not model:
            return None
        return {
            "id": model.id,
            "dataset_id": model.dataset_id,
            "name": model.name,
            "case_data": model.case_data or {},
            "tags": model.tags,
            "created_at": model.created_at.isoformat() if model.created_at else None,
        }

    def create_target_snapshot(
        self,
        target_id: str,
        agent_name: str = "",
        agent_type: str = "",
        config: dict = None,
        status: str = "ACTIVE",
    ) -> str:
        """创建评测对象快照"""
        from .domain import generate_uuid
        snapshot_id = generate_uuid()
        model = TargetSnapshotModel(
            id=snapshot_id,
            target_id=target_id,
            agent_name=agent_name,
            agent_type=agent_type,
            config=config or {},
            status=status,
        )
        self.session.add(model)
        self.session.commit()
        return snapshot_id

    def create_dataset_snapshot(
        self,
        dataset_id: str,
        name: str = "",
        description: str = "",
        purpose: str = "standard",
        archived: bool = False,
    ) -> str:
        """创建测评集快照"""
        from .domain import generate_uuid
        snapshot_id = generate_uuid()
        model = DatasetSnapshotModel(
            id=snapshot_id,
            dataset_id=dataset_id,
            name=name,
            description=description,
            purpose=purpose,
            archived=archived,
        )
        self.session.add(model)
        self.session.commit()
        return snapshot_id

    def create_evaluator_snapshot(self, evaluator_id: str, snapshot_data: dict) -> str:
        """创建评估器快照"""
        from .domain import generate_uuid
        snapshot_id = generate_uuid()
        model = EvaluatorSnapshotModel(
            id=snapshot_id,
            evaluator_id=evaluator_id,
            snapshot_data=snapshot_data,
        )
        self.session.add(model)
        self.session.commit()
        return snapshot_id

    def create_case_snapshot(
        self,
        case_id: str,
        name: str = "",
        initial_state: dict = None,
        category: str = "positive",
        difficulty: str = "medium",
        tags: str = "",
        notes: str = "",
    ) -> str:
        """创建用例快照"""
        from .domain import generate_uuid
        snapshot_id = generate_uuid()
        model = CaseSnapshotModel(
            id=snapshot_id,
            case_id=case_id,
            name=name,
            initial_state=initial_state or {},
            category=category,
            difficulty=difficulty,
            tags=tags,
            notes=notes,
        )
        self.session.add(model)
        self.session.commit()
        return snapshot_id

    def create_case_turn_snapshot(
        self,
        case_snapshot_id: str,
        case_turn_id: str = "",
        input: dict = None,
        expected_skill: str = "",
        expectations: str = "",
        required_tools: str = "",
        forbidden_tools: str = "",
        policy_rules: str = "",
        notes: str = "",
    ) -> str:
        """创建用例轮次快照"""
        from .domain import generate_uuid
        snapshot_id = generate_uuid()
        model = CaseTurnSnapshotModel(
            id=snapshot_id,
            case_snapshot_id=case_snapshot_id,
            case_turn_id=case_turn_id,
            input=input or {},
            expected_skill=expected_skill,
            expectations=expectations,
            required_tools=required_tools,
            forbidden_tools=forbidden_tools,
            policy_rules=policy_rules,
            notes=notes,
        )
        self.session.add(model)
        self.session.commit()
        return snapshot_id

    def get_target_snapshot(self, snapshot_id: str) -> dict | None:
        """获取评测对象快照"""
        model = self.session.query(TargetSnapshotModel).filter(TargetSnapshotModel.id == snapshot_id).first()
        if not model:
            return None
        return {
            "id": model.id,
            "target_id": model.target_id,
            "agent_name": model.agent_name or "",
            "agent_type": model.agent_type or "",
            "config": model.config or {},
            "status": model.status or "ACTIVE",
            "created_at": model.created_at.isoformat() if model.created_at else None,
        }

    def get_dataset_snapshot(self, snapshot_id: str) -> dict | None:
        """获取测评集快照"""
        model = self.session.query(DatasetSnapshotModel).filter(DatasetSnapshotModel.id == snapshot_id).first()
        if not model:
            return None
        return {
            "id": model.id,
            "dataset_id": model.dataset_id,
            "name": model.name or "",
            "description": model.description or "",
            "purpose": model.purpose or "standard",
            "archived": model.archived or False,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        }

    def get_case_snapshot(self, snapshot_id: str) -> dict | None:
        """获取用例快照"""
        model = self.session.query(CaseSnapshotModel).filter(CaseSnapshotModel.id == snapshot_id).first()
        if not model:
            return None
        return {
            "id": model.id,
            "case_id": model.case_id,
            "name": model.name or "",
            "initial_state": model.initial_state or {},
            "category": model.category or "positive",
            "difficulty": model.difficulty or "medium",
            "tags": model.tags or "",
            "notes": model.notes or "",
            "created_at": model.created_at.isoformat() if model.created_at else None,
        }

    def get_case_turn_snapshot(self, snapshot_id: str) -> dict | None:
        """获取用例轮次快照"""
        model = self.session.query(CaseTurnSnapshotModel).filter(CaseTurnSnapshotModel.id == snapshot_id).first()
        if not model:
            return None
        return {
            "id": model.id,
            "case_snapshot_id": model.case_snapshot_id,
            "case_turn_id": model.case_turn_id,
            "input": model.input or {},
            "expected_skill": model.expected_skill or "",
            "expectations": model.expectations or "",
            "required_tools": model.required_tools or "",
            "forbidden_tools": model.forbidden_tools or "",
            "policy_rules": model.policy_rules or "",
            "notes": model.notes or "",
            "created_at": model.created_at.isoformat() if model.created_at else None,
        }

    def get_evaluator_snapshot(self, snapshot_id: str) -> dict | None:
        """获取评估器快照"""
        model = self.session.query(EvaluatorSnapshotModel).filter(EvaluatorSnapshotModel.id == snapshot_id).first()
        if not model:
            return None
        return {
            "id": model.id,
            "evaluator_id": model.evaluator_id,
            "evaluator_type": model.evaluator_type,
            "snapshot_data": model.snapshot_data or {},
            "created_at": model.created_at.isoformat() if model.created_at else None,
        }

    def _to_task_entity(self, model: EvalTaskModel) -> EvalTask:
        """转换为任务实体"""
        from . import (
            EvaluatorEntity, EvalTask, TargetAgentEntity,
        )
        from .domain import utcnow
        task = EvalTask(
            id=model.id,
            task_name=model.task_name,
            target_id=model.target_id,
            dataset_id=model.dataset_id,
            evaluator_id=model.evaluator_id,
            status=TaskStatus(model.status) if model.status else TaskStatus.NEW,
            created_by=model.created_by or "",
            target_snapshot_id=model.target_snapshot_id or "",
            dataset_snapshot_id=model.dataset_snapshot_id or "",
            evaluator_snapshot_id=model.evaluator_snapshot_id or "",
            created_at=model.created_at if model.created_at else utcnow(),
            updated_at=model.updated_at if model.updated_at else utcnow(),
        )
        return task

    def _to_run_entity(self, model: TaskRunModel) -> TaskRun:
        """转换为执行记录实体"""
        from . import TaskRun, TaskStatus
        from .domain import utcnow
        return TaskRun(
            id=model.id,
            task_id=model.task_id,
            run_no=model.run_no,
            status=TaskStatus(model.status) if model.status else TaskStatus.NEW,
            target_snapshot_id=model.target_snapshot_id or "",
            dataset_snapshot_id=model.dataset_snapshot_id or "",
            evaluator_snapshot_id=model.evaluator_snapshot_id or "",
            total_cases=model.total_cases or 0,
            completed_cases=model.completed_cases or 0,
            passed_cases=model.passed_cases or 0,
            failed_cases=model.failed_cases or 0,
            avg_score=model.avg_score or 0.0,
            started_at=model.started_at,
            completed_at=model.completed_at,
            terminated_by=model.terminated_by or "",
            error_message=model.error_message or "",
            created_at=model.created_at if model.created_at else utcnow(),
        )

    def _to_case_dict(self, model: CaseModel) -> dict:
        """转换为用例字典"""
        return {
            "id": model.id,
            "dataset_id": model.dataset_id,
            "name": model.name or "",
            "case_data": model.case_data or {},
            "tags": model.tags or "",
            "created_at": model.created_at.isoformat() if model.created_at else None,
        }

    def _to_case_execution_dict(self, model: CaseExecutionModel) -> dict:
        """转换为用例执行记录字典"""
        return {
            "id": model.id,
            "run_id": model.run_id,
            "case_id": model.case_id,
            "status": model.status or "PENDING",
            "score": model.score or 0.0,
            "passed": model.passed or False,
            "agent_response": model.agent_response or "",
            "trace_data": model.trace_data or {},
            "evaluation_result_id": model.evaluation_result_id or "",
            "started_at": model.started_at.isoformat() if model.started_at else None,
            "completed_at": model.completed_at.isoformat() if model.completed_at else None,
            "created_at": model.created_at.isoformat() if model.created_at else None,
        }
