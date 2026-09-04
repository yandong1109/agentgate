"""
评估器模块。

提供 Evaluator 抽象基类和具体的评估器实现。
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .domain import CaseExecution, EvaluationResult, EvaluatorType

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class Evaluator(ABC):
    """评估器抽象父类"""

    def set_config(self, config: dict) -> None:
        """设置评估器配置"""
        self.config = config

    @abstractmethod
    def calculate(self, case_execution: CaseExecution) -> EvaluationResult:
        """
        计算评估结果
        :param case_execution: 用例执行记录
        :return: 评估结果
        """
        pass


class RuleEvaluator(Evaluator):
    """规则评估器"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._rules = self.config.get("rules", [])

    def calculate(self, case_execution: CaseExecution) -> EvaluationResult:
        """
        使用规则进行评估
        :param case_execution: 用例执行记录
        :return: 评估结果
        """
        agent_response = case_execution.agent_response
        score = 0.0
        reasons = []
        details = {}

        passed_count = 0
        total_rules = len(self._rules)

        for rule in self._rules:
            rule_type = rule.get("type", "contains")
            rule_value = rule.get("value", "")
            rule_weight = rule.get("weight", 1.0)

            if rule_type == "contains":
                matched = rule_value.lower() in agent_response.lower()
                if matched:
                    passed_count += 1
                    reasons.append(f"规则通过：包含 '{rule_value}'")
                else:
                    reasons.append(f"规则失败：未包含 '{rule_value}'")

            elif rule_type == "not_contains":
                matched = rule_value.lower() not in agent_response.lower()
                if matched:
                    passed_count += 1
                    reasons.append(f"规则通过：不包含 '{rule_value}'")
                else:
                    reasons.append(f"规则失败：包含 '{rule_value}'")

            elif rule_type == "regex":
                matched = bool(re.search(rule_value, agent_response))
                if matched:
                    passed_count += 1
                    reasons.append(f"规则通过：匹配正则 '{rule_value}'")
                else:
                    reasons.append(f"规则失败：正则 '{rule_value}' 不匹配")

            elif rule_type == "equals":
                matched = agent_response.strip() == rule_value.strip()
                if matched:
                    passed_count += 1
                    reasons.append(f"规则通过：完全匹配")
                else:
                    reasons.append(f"规则失败：内容不匹配")

            details[rule_type] = {
                "value": rule_value,
                "passed": matched
            }

        if total_rules > 0:
            score = (passed_count / total_rules) * 100
        else:
            score = 100.0

        passed = score >= self.config.get("pass_threshold", 60)

        return EvaluationResult(
            score=score,
            passed=passed,
            reasons=reasons,
            details=details
        )


class LLMJudgeEvaluator(Evaluator):
    """LLM评估器（使用大模型判断）"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._model = self.config.get("model", "gpt-4")
        self._api_key = self.config.get("api_key", "")
        self._prompt_template = self.config.get("prompt_template", "")

    def calculate(self, case_execution: CaseExecution) -> EvaluationResult:
        """
        使用LLM进行评估
        :param case_execution: 用例执行记录
        :return: 评估结果
        """
        agent_response = case_execution.agent_response
        trace_data = case_execution.trace_data

        logger.info(f"LLMJudgeEvaluator calculating with model: {self._model}")

        prompt = self._build_prompt(agent_response, trace_data)

        simulated_score = 85.0
        simulated_passed = True
        reasons = [f"LLM评估通过（模拟）：模型 {self._model} 判断为合格"]
        details = {
            "model": self._model,
            "prompt_length": len(prompt),
            "response_length": len(agent_response)
        }

        return EvaluationResult(
            score=simulated_score,
            passed=simulated_passed,
            reasons=reasons,
            details=details
        )

    def _build_prompt(self, agent_response: str, trace_data: dict) -> str:
        """构建评估提示词"""
        if self._prompt_template:
            return self._prompt_template.format(response=agent_response)

        default_template = f"""请评估以下智能体回复的质量：

回复内容：
{agent_response}

请从准确性、完整性、专业性三个维度进行评分（0-100分），并判断是否通过。
输出格式：{{"score": 分数, "passed": true/false, "reason": "评估理由"}}
"""
        return default_template


class CompositeEvaluator(Evaluator):
    """复合评估器（组合多个评估器）"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._evaluators = []
        self._weights = self.config.get("weights", [])
        self._pass_threshold = self.config.get("pass_threshold", 60)
        self._setup_evaluators()

    def _setup_evaluators(self) -> None:
        """初始化子评估器"""
        evaluator_configs = self.config.get("evaluators", [])

        for idx, eval_config in enumerate(evaluator_configs):
            eval_type = eval_config.get("type", "RULE")
            eval_weight = self._weights[idx] if idx < len(self._weights) else 1.0

            if eval_type == "RULE":
                evaluator = RuleEvaluator(eval_config.get("config", {}))
            elif eval_type == "LLM":
                evaluator = LLMJudgeEvaluator(eval_config.get("config", {}))
            else:
                continue

            evaluator.set_config(eval_config.get("config", {}))
            self._evaluators.append((evaluator, eval_weight))

    def calculate(self, case_execution: CaseExecution) -> EvaluationResult:
        """
        使用复合评估器进行评估
        :param case_execution: 用例执行记录
        :return: 评估结果
        """
        total_score = 0.0
        total_weight = 0.0
        all_reasons = []
        all_details = {}

        for evaluator, weight in self._evaluators:
            result = evaluator.calculate(case_execution)
            total_score += result.score * weight
            total_weight += weight
            all_reasons.extend(result.reasons)
            all_details[type(evaluator).__name__] = {
                "score": result.score,
                "weight": weight,
                "passed": result.passed
            }

        final_score = total_score / total_weight if total_weight > 0 else 0.0
        passed = final_score >= self._pass_threshold

        return EvaluationResult(
            score=final_score,
            passed=passed,
            reasons=all_reasons,
            details=all_details
        )


class EvaluatorFactory:
    """评估器工厂类，根据类型和配置创建评估器实例"""

    @staticmethod
    def create(evaluator_type: str | EvaluatorType, config: dict | None = None) -> Evaluator:
        """
        创建评估器实例
        :param evaluator_type: 评估器类型（RULE/LLM/COMPOSITE）
        :param config: 评估器配置
        :return: Evaluator实例
        """
        if isinstance(evaluator_type, str):
            evaluator_type = EvaluatorType(evaluator_type)

        evaluators = {
            EvaluatorType.RULE: RuleEvaluator,
            EvaluatorType.LLM: LLMJudgeEvaluator,
            EvaluatorType.COMPOSITE: CompositeEvaluator,
        }

        evaluator_class = evaluators.get(evaluator_type)
        if not evaluator_class:
            raise ValueError(f"Unknown evaluator type: {evaluator_type}")

        evaluator = evaluator_class(config)
        evaluator.set_config(config or {})
        return evaluator
