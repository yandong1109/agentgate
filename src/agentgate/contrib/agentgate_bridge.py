"""AgentGate ↔ trace-sdk 桥接（运行在被测 Agent 进程内）。

职责（见 docs/trace/trace-sdk-integration-plan.md §关联桥接设计）：
- 从 AgentGate invoke 请求体/头取关联（run/case/turn/invocation）与 trace_id；
- 把关联写入事件 metadata（trace-sdk 事件模型的关联通道）；
- trace_id 注入：单轮用引擎经 traceparent 传来的 trace_id（32-hex，
  与 pending_trace_correlation 精确匹配）；多轮每轮独立 trace（靠 metadata 关联）；
- 响应返回前全部落盘（file 后端为 write-through，天然满足 flush 及时性）。

双模式：
- 轻量 writer（默认，零依赖）：直接产出 trace-sdk file 后端格式的事件 JSONL，
  目录 <root>/<project_id>/<session_id>/<trace_id>.jsonl，session_id = run_id；
- 真 SDK 模式（sdk=True 且安装了 trace_sdk）：包装 TraceClient +
  CallbackHandler（trace_context 注入 + metadata），供 LangChain Agent 使用。

本文件自包含：不 import agentgate（Agent 侧无需安装 AgentGate）。
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

DEFAULT_PROJECT_ID = "agentgate"


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def extract_trace_id(traceparent: str) -> str:
    """从 traceparent 头取 32-hex trace_id；缺失时自产（依赖 metadata 关联）。"""
    parts = (traceparent or "").split("-")
    if len(parts) >= 2 and len(parts[1]) == 32:
        return parts[1]
    return uuid4().hex


def correlate(body: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
    """从 invoke 请求构造事件 metadata（关联契约：agentgate.* 键）。"""
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    trace_id = extract_trace_id(headers.get("traceparent", ""))
    metadata = {
        "agentgate.run.id": str(body.get("run_id", "")),
        "agentgate.case.id": str(body.get("case_id", "")),
        "agentgate.invocation.id": str(body.get("invocation_id", "")),
    }
    if body.get("turn_id"):
        metadata["agentgate.turn.id"] = str(body["turn_id"])
    return {"trace_id": trace_id, "metadata": {k: v for k, v in metadata.items() if v}}


class LightEventWriter:
    """轻量事件 writer：trace-sdk file 后端格式（JSONL，write-through）。"""

    def __init__(self, root: str | Path, project_id: str = DEFAULT_PROJECT_ID) -> None:
        self.root = Path(root)
        self.project_id = project_id
        self._handles: dict[Path, Any] = {}

    def write_event(self, event: dict[str, Any]) -> None:
        session = str(event.get("session_id") or "_no_session")
        trace_id = str(event.get("trace_id") or "_no_trace")
        path = self.root / self.project_id / session / f"{trace_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def flush(self) -> None:
        """file 模式为 write-through；保留方法以对齐 SDK 模式接口。"""


class _SdkWriter:
    """真 trace_sdk 模式的 writer 适配（延迟 import，未安装则报错）。"""

    def __init__(self, client: Any) -> None:
        self.client = client

    def write_event(self, event: dict[str, Any]) -> None:
        self.client.collector._emit(dict(event))  # noqa: SLF001 - SDK 内部桥接

    def flush(self) -> None:
        self.client.flush()


class TurnTrace:
    """一轮（或单轮用例）的桥接上下文：span 事件 + 终态 TraceEvent。"""

    def __init__(
        self,
        writer: LightEventWriter | _SdkWriter,
        *,
        project_id: str,
        session_id: str,
        trace_id: str,
        metadata: dict[str, Any],
        root_span_name: str = "agent.invoke",
    ) -> None:
        self._writer = writer
        self._base = {
            "project_id": project_id,
            "session_id": session_id,
            "trace_id": trace_id,
            "created_at": _utcnow_iso(),
        }
        self._metadata = metadata
        self._root_span_id = uuid4().hex[:16]
        self._started = False
        self._finished = False
        self._root_span_name = root_span_name

    def start(self) -> None:
        self._started = True
        self._writer.write_event({
            **self._base,
            "event_type": "span",
            "span_id": self._root_span_id,
            "parent_span_id": None,
            "name": self._root_span_name,
            "span_type": "agent",
            "metadata": dict(self._metadata),
            "started_at": _utcnow_iso(),
        })

    def tool(self, name: str, args: dict[str, Any] | None = None) -> None:
        """记录工具调用（span.name = 工具名，评测器按名匹配的契约）。"""
        if not self._started:
            self.start()
        self._writer.write_event({
            **self._base,
            "event_type": "span",
            "span_id": uuid4().hex[:16],
            "parent_span_id": self._root_span_id,
            "name": name,
            "span_type": "tool",
            "tool_name": name,
            "input": args or {},
            "metadata": dict(self._metadata),
            "started_at": _utcnow_iso(),
        })

    def finish(
        self, *, output: Any, final_state: dict[str, Any] | None = None,
        status: str = "success",
        error_info: dict[str, Any] | None = None,
    ) -> None:
        """终态：TraceEvent 落地（= trace_complete / turn_complete / final_output /
        final_state）。final_state 经 metadata 携带（评测终态断言的数据源）。"""
        if not self._started:
            self.start()
        if self._finished:
            return
        self._finished = True
        metadata = dict(self._metadata)
        if final_state is not None:
            metadata["agentgate.final_state.json"] = json.dumps(
                final_state, ensure_ascii=False, sort_keys=True
            )
        event: dict[str, Any] = {
            **self._base,
            "event_type": "trace",
            "event_id": uuid4().hex,
            "status": status,
            "output": output,
            "metadata": metadata,
        }
        if error_info:
            event["error_info"] = error_info
        self._writer.write_event(event)


class AgentGateBridge:
    """invoke 入口级桥接：解析关联 → 逐轮 TurnTrace → 响应前 flush。"""

    def __init__(
        self,
        *,
        output_root: str | Path | None = None,
        project_id: str = DEFAULT_PROJECT_ID,
        client: Any | None = None,
    ) -> None:
        """output_root 为轻量模式必填；client 提供时走真 SDK 模式。"""
        if client is not None:
            self._writer: LightEventWriter | _SdkWriter = _SdkWriter(client)
            self._root = None
        else:
            root = output_root or os.getenv("AGENTGATE_TRACE_SDK_FILE_ROOT")
            if not root:
                raise ValueError(
                    "需要 output_root 或环境变量 AGENTGATE_TRACE_SDK_FILE_ROOT"
                )
            self._writer = LightEventWriter(root)
            self._root = Path(root)
        self.project_id = project_id

    def turn_traces(
        self, body: dict[str, Any], headers: dict[str, str] | None = None,
    ) -> list[TurnTrace]:
        """按 invoke 请求构造轮次上下文列表。

        - 单轮（扁平 input 或单元素 turns）：用引擎 trace_id（pending 精确匹配）；
        - 多轮：每轮独立 trace_id（靠 metadata 关联聚合到同一 run/case）。
        """
        correlation = correlate(body, headers)
        trace_id = correlation["trace_id"]
        metadata = correlation["metadata"]
        run_id = metadata.get("agentgate.run.id", "")

        turns = (body.get("input") or {}).get("turns")
        if isinstance(turns, list) and len(turns) > 1:
            traces = []
            for index, turn in enumerate(turns):
                turn_meta = dict(metadata)
                if turn.get("turn_id"):
                    turn_meta["agentgate.turn.id"] = str(turn["turn_id"])
                # 派生 trace_id：保持确定性且互不相同（metadata 关联兜底）
                derived = f"{trace_id[:24]}{index:08x}"
                traces.append(TurnTrace(
                    self._writer, project_id=self.project_id,
                    session_id=run_id, trace_id=derived, metadata=turn_meta,
                ))
            return traces

        turn_meta = dict(metadata)
        if body.get("turn_id"):
            turn_meta["agentgate.turn.id"] = str(body["turn_id"])
        elif isinstance(turns, list) and turns and turns[0].get("turn_id"):
            turn_meta["agentgate.turn.id"] = str(turns[0]["turn_id"])
        return [TurnTrace(
            self._writer, project_id=self.project_id,
            session_id=run_id, trace_id=trace_id, metadata=turn_meta,
        )]

    def flush(self) -> None:
        self._writer.flush()
