"""Ticket-Approv-Agent：基于 LangChain 架构的工单审批 Agent（接口打通版）。

本地 Runnable shim 镜像 langchain_core.runnables.RunnableLambda 的接口，
待安装真实 langchain 后可直接替换 import 而不动链路组装代码。
"""

from __future__ import annotations

from typing import Any, Callable


class RunnableLambda:
    """langchain_core.runnables.RunnableLambda 的最小本地镜像（stub 模式）。"""

    def __init__(self, func: Callable[[dict], dict], name: str = "") -> None:
        self.func = func
        self.name = name or getattr(func, "__name__", "runnable")

    def invoke(self, input: dict, config: dict | None = None) -> dict:
        return self.func(input)

    def __or__(self, other: "RunnableLambda | RunnableSequence") -> "RunnableSequence":
        return RunnableSequence([self, other])

    def __repr__(self) -> str:  # 便于日志观察链路
        return f"RunnableLambda({self.name})"


class RunnableSequence:
    """langchain_core.runnables.RunnableSequence 的最小本地镜像。"""

    def __init__(self, steps: list[RunnableLambda]) -> None:
        self.steps = steps

    def invoke(self, input: dict, config: dict | None = None) -> dict:
        data = input
        for step in self.steps:
            data = step.invoke(data, config)
        return data

    def __or__(self, other: RunnableLambda) -> "RunnableSequence":
        return RunnableSequence([*self.steps, other])

    @property
    def names(self) -> list[str]:
        return [step.name for step in self.steps]


# ── 链路步骤（stub 实现；真实版本换成 LLM 调用）──────────────────────


def _classify_ticket(ctx: dict) -> dict:
    """Step 1 · 工单分类：识别工单类型与风险等级。"""
    ticket = ctx["input"]
    ctx["ticket_id"] = ticket.get("ticket_id") or ticket.get("application_id") or "T-000"
    ctx["title"] = ticket.get("title") or ticket.get("skill") or "generic_ticket"
    risk = str(
        ticket.get("risk") or ticket.get("priority") or "low"
    ).lower()
    ctx["risk_level"] = risk
    return ctx


def _decide_approval(ctx: dict) -> dict:
    """Step 2 · 审批决策：高风险/大额工单转人工，其余直接批准。

    真实实现替换点：这里应调用 LLM（如 ChatOpenAI）+ 工具执行；
    stub 用确定性规则保证无 LLM Key 也可联调。
    """
    ticket = ctx["input"]
    try:
        amount = float(ticket.get("amount") or 0)
    except (TypeError, ValueError):
        amount = 0.0

    needs_review = ctx["risk_level"] in {"high", "urgent"} or amount > 50_000

    if needs_review:
        ctx["decision"] = "human_review"
        ctx["tool_events"] = [
            {"tool": "review_ticket", "args": {"ticket_id": ctx["ticket_id"], "human_review": True}},
        ]
        ctx["output"] = {
            "message": f"工单 {ctx['ticket_id']} 风险较高，已转人工审核",
            "status": "pending_review",
        }
        ctx["final_state"] = {
            "ticket_id": ctx["ticket_id"],
            "status": "pending_review",
            "approved": False,
            "human_review": True,
        }
    else:
        ctx["decision"] = "auto_approved"
        ctx["tool_events"] = [
            {"tool": "approve_ticket", "args": {"ticket_id": ctx["ticket_id"], "approved": True}},
        ]
        ctx["output"] = {
            "message": f"工单 {ctx['ticket_id']} 已自动批准",
            "status": "approved",
        }
        ctx["final_state"] = {
            "ticket_id": ctx["ticket_id"],
            "status": "approved",
            "approved": True,
            "human_review": False,
        }
    return ctx


def _build_state(ctx: dict) -> dict:
    """Step 3 · 状态归集：合并跨轮业务状态并产出最终快照。"""
    previous_state = ctx.get("state") or {}
    ctx["final_state"] = {**previous_state, **ctx["final_state"]}
    return ctx


# ── 链路组装（LangChain 风格：step | step | step）─────────────────────

classify_ticket = RunnableLambda(_classify_ticket, "classify_ticket")
decide_approval = RunnableLambda(_decide_approval, "decide_approval")
build_state = RunnableLambda(_build_state, "build_state")

ticket_chain = classify_ticket | decide_approval | build_state


class TicketApprovAgent:
    """Agent 门面：把 invoke 输入喂给链路，产出契约级 output/state/tool 事件。"""

    name = "Ticket-Approv-Agent"

    def invoke(self, input: dict, state: dict) -> dict:
        ctx = {"input": input, "state": state}
        result = ticket_chain.invoke(ctx)
        return {
            "output": result["output"],
            "final_state": result["final_state"],
            "tool_events": result["tool_events"],
        }
