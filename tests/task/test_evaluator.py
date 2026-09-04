"""
Evaluator tests.
"""

import pytest
from agentgate.task.domain import CaseExecution, EvaluationResult, EvaluatorType
from agentgate.task.evaluator import (
    CompositeEvaluator,
    EvaluatorFactory,
    LLMJudgeEvaluator,
    RuleEvaluator,
)


def test_rule_evaluator_contains():
    """测试规则评估器 - contains规则"""
    evaluator = RuleEvaluator({
        "rules": [
            {"type": "contains", "value": "hello", "weight": 1.0},
        ],
        "pass_threshold": 60,
    })

    execution = CaseExecution(
        run_id="run-1",
        case_id="case-1",
        agent_response="Hello, this is a test response",
    )

    result = evaluator.calculate(execution)
    assert result.passed is True
    assert result.score == 100.0
    assert len(result.reasons) == 1


def test_rule_evaluator_not_contains():
    """测试规则评估器 - not_contains规则"""
    evaluator = RuleEvaluator({
        "rules": [
            {"type": "not_contains", "value": "error", "weight": 1.0},
        ],
        "pass_threshold": 60,
    })

    execution = CaseExecution(
        run_id="run-1",
        case_id="case-1",
        agent_response="Success! All clear here.",
    )

    result = evaluator.calculate(execution)
    assert result.passed is True
    assert result.score == 100.0


def test_rule_evaluator_regex():
    """测试规则评估器 - regex规则"""
    evaluator = RuleEvaluator({
        "rules": [
            {"type": "regex", "value": r"\d{3}-\d{4}", "weight": 1.0},
        ],
        "pass_threshold": 60,
    })

    execution = CaseExecution(
        run_id="run-1",
        case_id="case-1",
        agent_response="My phone is 123-4567",
    )

    result = evaluator.calculate(execution)
    assert result.passed is True
    assert result.score == 100.0


def test_rule_evaluator_multiple_rules():
    """测试规则评估器 - 多规则"""
    evaluator = RuleEvaluator({
        "rules": [
            {"type": "contains", "value": "hello", "weight": 1.0},
            {"type": "contains", "value": "thanks", "weight": 1.0},
        ],
        "pass_threshold": 50,
    })

    execution = CaseExecution(
        run_id="run-1",
        case_id="case-1",
        agent_response="Hello, thanks for your help",
    )

    result = evaluator.calculate(execution)
    assert result.passed is True
    assert result.score == 100.0


def test_rule_evaluator_fail():
    """测试规则评估器 - 失败"""
    evaluator = RuleEvaluator({
        "rules": [
            {"type": "contains", "value": "hello", "weight": 1.0},
        ],
        "pass_threshold": 60,
    })

    execution = CaseExecution(
        run_id="run-1",
        case_id="case-1",
        agent_response="Goodbye, see you later",
    )

    result = evaluator.calculate(execution)
    assert result.passed is False
    assert result.score == 0.0


def test_llm_judge_evaluator():
    """测试LLM评估器"""
    evaluator = LLMJudgeEvaluator({
        "model": "gpt-4",
        "api_key": "test-key",
    })

    execution = CaseExecution(
        run_id="run-1",
        case_id="case-1",
        agent_response="This is a helpful response",
    )

    result = evaluator.calculate(execution)
    assert result.passed is True
    assert result.score > 0
    assert len(result.reasons) > 0


def test_composite_evaluator():
    """测试复合评估器"""
    evaluator = CompositeEvaluator({
        "evaluators": [
            {
                "type": "RULE",
                "config": {
                    "rules": [{"type": "contains", "value": "ok", "weight": 1.0}],
                    "pass_threshold": 60,
                }
            },
            {
                "type": "LLM",
                "config": {"model": "gpt-4", "api_key": "test-key"}
            },
        ],
        "weights": [1.0, 1.0],
        "pass_threshold": 60,
    })

    execution = CaseExecution(
        run_id="run-1",
        case_id="case-1",
        agent_response="Everything is ok here",
    )

    result = evaluator.calculate(execution)
    assert result.score >= 0


def test_evaluator_factory_rule():
    """测试评估器工厂 - RULE"""
    evaluator = EvaluatorFactory.create(
        EvaluatorType.RULE,
        {"rules": [{"type": "contains", "value": "test"}]}
    )
    assert isinstance(evaluator, RuleEvaluator)


def test_evaluator_factory_llm():
    """测试评估器工厂 - LLM"""
    evaluator = EvaluatorFactory.create(
        EvaluatorType.LLM,
        {"model": "gpt-4"}
    )
    assert isinstance(evaluator, LLMJudgeEvaluator)


def test_evaluator_factory_composite():
    """测试评估器工厂 - COMPOSITE"""
    evaluator = EvaluatorFactory.create(
        EvaluatorType.COMPOSITE,
        {"evaluators": [], "weights": []}
    )
    assert isinstance(evaluator, CompositeEvaluator)


def test_evaluator_factory_string_type():
    """测试评估器工厂 - 字符串类型"""
    evaluator = EvaluatorFactory.create("RULE", {})
    assert isinstance(evaluator, RuleEvaluator)
