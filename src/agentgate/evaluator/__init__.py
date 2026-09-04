"""Public evaluator API."""

from agentgate.domain import Dimension, RuleEvaluatorSpec, Severity

from . import operators as _operators
from . import rules as _rules
from .runner import evaluate_case
from .validation import validate_evaluation_plan

EVALUATORS = (
    RuleEvaluatorSpec(
        id="skill-routing", name="技能路由", evaluator_type="skill_routing",
        operator="equals", operator_version="1", dimension=Dimension.ROUTING,
        metric="skill_routing_accuracy",
    ),
    RuleEvaluatorSpec(
        id="required-tool", name="必需工具", evaluator_type="required_tool",
        operator="contains_all", operator_version="1", dimension=Dimension.TOOL_USE,
        metric="tool_coverage",
    ),
    RuleEvaluatorSpec(
        id="forbidden-tool", name="禁用工具", evaluator_type="forbidden_tool",
        operator="contains_none", operator_version="1", dimension=Dimension.TOOL_USE,
        metric="forbidden_tool_compliance", severity=Severity.BLOCKING,
    ),
    RuleEvaluatorSpec(
        id="tool-arguments", name="工具参数", evaluator_type="tool_arguments",
        dimension=Dimension.TOOL_USE, metric="tool_argument_accuracy",
    ),
    RuleEvaluatorSpec(
        id="final-state", name="最终状态", evaluator_type="final_state",
        dimension=Dimension.STATE, metric="final_state_match",
    ),
    RuleEvaluatorSpec(
        id="final-output", name="最终输出", evaluator_type="final_output",
        dimension=Dimension.ANSWER, metric="final_output_match",
    ),
    RuleEvaluatorSpec(
        id="policy-compliance", name="策略合规", evaluator_type="policy_compliance",
        dimension=Dimension.SAFETY, metric="policy_compliance",
        severity=Severity.BLOCKING,
    ),
)

__all__ = ["EVALUATORS", "evaluate_case", "validate_evaluation_plan"]
