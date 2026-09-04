"""
Domain models tests.
"""

import pytest
from agentgate.task.domain import (
    AgentType,
    EvaluationResult,
    EvaluatorType,
    EvaluatorEntity,
    EvalTask,
    TaskRun,
    TaskStatus,
    TargetAgentEntity,
    TraceInfo,
    generate_uuid,
    utcnow,
)
from agentgate.domain.case import Case, Dataset


def test_trace_info():
    """测试TraceInfo"""
    trace = TraceInfo(
        session_id="test-session-1",
        rounds=[{"round": 1, "user_input": "hello", "agent_response": "hi"}],
        tool_calls=[{"tool": "test_tool", "input": "test"}],
        total_duration_ms=100,
    )
    assert trace.session_id == "test-session-1"
    assert len(trace.rounds) == 1
    assert len(trace.tool_calls) == 1
    assert trace.total_duration_ms == 100


def test_evaluation_result():
    """测试EvaluationResult"""
    result = EvaluationResult(
        score=95.5,
        passed=True,
        reasons=["规则1通过", "规则2通过"],
        details={"accuracy": 100},
    )
    assert result.score == 95.5
    assert result.passed is True
    assert len(result.reasons) == 2
    assert result.details["accuracy"] == 100


def test_target_agent_entity():
    """测试TargetAgentEntity"""
    agent = TargetAgentEntity(
        agent_name="Test Agent",
        agent_type=AgentType.REMOTE_AGENT,
        config={"remote_url": "https://api.example.com"},
    )
    assert agent.agent_name == "Test Agent"
    assert agent.agent_type == AgentType.REMOTE_AGENT
    assert agent.status == "ACTIVE"

    data = agent.to_dict()
    assert data["agent_name"] == "Test Agent"
    assert data["agent_type"] == "REMOTE_AGENT"


def test_dataset():
    """测试Dataset"""
    dataset = Dataset(
        name="Test Dataset",
        description="A test dataset",
    )
    assert dataset.name == "Test Dataset"
    assert dataset.archived == False

    data = dataset.model_dump(mode="json")
    assert data["name"] == "Test Dataset"
    assert data["description"] == "A test dataset"


def test_case():
    """测试Case"""
    from agentgate.domain.case import CaseTurn

    case = Case(
        name="Test Case",
        turns=(
            CaseTurn(
                input={"user_input": "Hello", "expected_response": "Hi"},
            ),
            CaseTurn(
                input={"user_input": "How are you?", "expected_response": "I'm fine"},
            ),
        ),
        tags=("test", "hello"),
    )
    assert case.name == "Test Case"

    turns = case.turns
    assert len(turns) == 2
    assert turns[0].input["user_input"] == "Hello"


def test_evaluator_entity():
    """测试EvaluatorEntity"""
    evaluator = EvaluatorEntity(
        name="Rule Evaluator",
        evaluator_type=EvaluatorType.RULE,
        config={"rules": [{"type": "contains", "value": "ok"}]},
    )
    assert evaluator.name == "Rule Evaluator"
    assert evaluator.evaluator_type == EvaluatorType.RULE

    data = evaluator.to_dict()
    assert data["name"] == "Rule Evaluator"
    assert data["evaluator_type"] == "RULE"


def test_eval_task():
    """测试EvalTask"""
    task = EvalTask(
        task_name="Test Task",
        target_id="target-123",
        dataset_id="dataset-456",
        evaluator_id="evaluator-789",
        created_by="admin",
    )
    assert task.task_name == "Test Task"
    assert task.status == TaskStatus.NEW

    data = task.to_dict()
    assert data["task_name"] == "Test Task"
    assert data["status"] == "NEW"


def test_task_run():
    """测试TaskRun"""
    run = TaskRun(
        task_id="task-123",
        run_no=1,
        status=TaskStatus.RUNNING,
        total_cases=100,
        completed_cases=50,
        passed_cases=45,
        failed_cases=5,
        avg_score=88.5,
    )
    assert run.task_id == "task-123"
    assert run.run_no == 1
    assert run.total_cases == 100
    assert run.completed_cases == 50

    data = run.to_dict()
    assert data["run_no"] == 1
    assert data["pass_rate"] == 45.0


def test_task_status_enum():
    """测试TaskStatus枚举"""
    assert TaskStatus.NEW.value == "NEW"
    assert TaskStatus.PENDING.value == "PENDING"
    assert TaskStatus.RUNNING.value == "RUNNING"
    assert TaskStatus.SUCCESS.value == "SUCCESS"
    assert TaskStatus.FAIL.value == "FAIL"
    assert TaskStatus.TERMINATED.value == "TERMINATED"


def test_agent_type_enum():
    """测试AgentType枚举"""
    assert AgentType.SKILL.value == "SKILL"
    assert AgentType.REMOTE_AGENT.value == "REMOTE_AGENT"
    assert AgentType.AGENT_WORKFLOW.value == "AGENT_WORKFLOW"


def test_evaluator_type_enum():
    """测试EvaluatorType枚举"""
    assert EvaluatorType.RULE.value == "RULE"
    assert EvaluatorType.LLM.value == "LLM"
    assert EvaluatorType.COMPOSITE.value == "COMPOSITE"


def test_generate_uuid():
    """测试UUID生成"""
    uuid1 = generate_uuid()
    uuid2 = generate_uuid()
    assert uuid1 != uuid2
    assert len(uuid1) == 36


def test_utcnow():
    """测试UTC时间生成"""
    now = utcnow()
    assert now is not None


def test_utcnow_returns_beijing_time():
    """测试utcnow返回北京时间(UTC+8)"""
    from datetime import datetime, timezone, timedelta
    BEIJING_TZ = timezone(timedelta(hours=8))

    now = utcnow()
    beijing_now = datetime.now(BEIJING_TZ)

    # 误差在2秒内（考虑执行时间）
    diff = abs((now - beijing_now).total_seconds())
    assert diff < 2, f"utcnow返回的时间与北京时间差异超过2秒: utcnow={now}, 北京时间={beijing_now}"

    # 验证时区信息
    assert now.tzinfo is not None, "utcnow返回的时间应该有时区信息"
    assert now.tzinfo == BEIJING_TZ, f"utcnow应该返回北京时间(UTC+8)，实际返回: {now.tzinfo}"
