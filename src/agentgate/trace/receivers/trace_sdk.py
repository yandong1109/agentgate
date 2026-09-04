"""trace-sdk 事件接收器（file 模式；Redis 模式 G2 后补）。

从 trace-sdk file 后端的输出目录增量拉取事件 JSONL，归一化后走既有
``TraceIngestionService.ingest`` 管线（与 OTLP 路径在 NormalizedSpan 汇合）。

目录约定（对齐 trace-sdk file exporter）：
    <root>/<project_id>/<session_id>/<trace_id>.jsonl    主事件流（本接收器消费）
    <root>/<project_id>/<session>/<trace>/spn/*.json     LLM 请求独立文件（暂不消费）

容错语义：
- 半行容错：行尾无换行的最后半行留待下一轮重读（设计验收 #35）；
- 幂等：按文件记录已读字节 offset；重复内容由批次哈希 + span 身份去重兜底；
- 无关联事件（resolver 未命中且无 metadata 关联）被归一化层拒绝，不阻断其他事件。
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

from agentgate.trace.models import IngestionReport, OtlpIngestionLimits
from agentgate.trace.normalizer import normalize_trace_sdk_events
from agentgate.trace.service import TraceIngestionService

logger = logging.getLogger(__name__)


class TraceSdkFileReceiver:
    """监控 trace-sdk file 输出目录并增量摄取事件。线程安全（可在守护线程运行）。"""

    def __init__(
        self,
        root: str | Path,
        repository: Any,
        *,
        limits: OtlpIngestionLimits | None = None,
        service: TraceIngestionService | None = None,
    ) -> None:
        self.root = Path(root)
        self.repository = repository
        self.limits = limits
        self.service = service or TraceIngestionService(repository)
        self._offsets: dict[str, int] = {}
        self._lock = threading.Lock()

    def _resolver(self, trace_id: str):
        pending = getattr(self.repository, "get_pending_trace", None)
        if pending is None:
            return None
        record = pending(trace_id)
        if record is None:
            return None
        return (record.run_id, record.case_id, record.invocation_id)

    def _read_new_lines(self, path: Path) -> tuple[list[dict[str, Any]], int]:
        """读取 offset 之后完整结束的行；返回 (事件列表, 新 offset)。"""
        key = str(path)
        offset = self._offsets.get(key, 0)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            return [], offset
        chunk = data[offset:]
        if not chunk:
            return [], offset
        # 半行容错：最后一个换行符之后的内容留待下轮
        last_newline = chunk.rfind(b"\n")
        if last_newline < 0:
            return [], offset
        complete = chunk[: last_newline + 1]
        events: list[dict[str, Any]] = []
        for line in complete.decode("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("跳过无法解析的事件行: %s", path)
                continue
            if isinstance(event, dict):
                events.append(event)
        new_offset = offset + last_newline + 1
        return events, new_offset

    def poll_once(self) -> int:
        """扫描一次目录，摄取有新增内容的文件。返回摄取的批次数。"""
        if not self.root.is_dir():
            return 0
        ingested = 0
        # 排序保证确定性（重放同状态得到同结果）
        for path in sorted(self.root.rglob("*.jsonl")):
            with self._lock:
                events, new_offset = self._read_new_lines(path)
                if not events:
                    continue
                batch = normalize_trace_sdk_events(
                    events, self.limits, correlation_resolver=self._resolver,
                )
                self._offsets[str(path)] = new_offset
            report: IngestionReport = self.service.ingest(batch)
            ingested += 1
            if report.rejected_spans or report.errors:
                logger.info(
                    "trace-sdk 批次 %s：accepted=%d duplicate=%d rejected=%d",
                    path.name, report.accepted_spans, report.duplicate_spans,
                    report.rejected_spans,
                )
        return ingested

    def run_forever(
        self, *, interval_seconds: float = 1.0,
        stop: threading.Event | None = None,
    ) -> None:
        """守护线程主循环：轮询直到 stop 置位。"""
        stop = stop or threading.Event()
        logger.info("trace-sdk file 接收器已启动: root=%s", self.root)
        while not stop.is_set():
            try:
                self.poll_once()
            except Exception as exc:  # noqa: BLE001 - 单轮失败不终止接收器
                logger.warning("trace-sdk 拉取失败（下轮重试）: %s", exc)
            stop.wait(interval_seconds)
        logger.info("trace-sdk file 接收器已停止")
