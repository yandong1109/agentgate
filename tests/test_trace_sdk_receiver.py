"""L2 集成测试：trace-sdk file 接收器全链路（拉取→归一化→merge→COMPLETE）。

覆盖验收 #32-36：拉取幂等、半行容错、pending 关联、trace_complete 收敛。
"""

import json
from datetime import UTC, datetime

from agentgate.domain import (
    DatasetVersion,
    DatasetVersionStatus,
    GateSpec,
    MetricPlan,
    Run,
    RunSnapshot,
    RunStatus,
    TargetRef,
    TargetSnapshot,
    TargetType,
)
from agentgate.evaluator import EVALUATORS
from agentgate.storage.sqlite import SQLiteRepository
from agentgate.trace.receivers import TraceSdkFileReceiver

TRACE_ID = "cd" * 16


def _dataset():
    from agentgate.domain import Case, CaseTurn

    case = Case(
        id="c1", name="case-1",
        turns=(CaseTurn(id="t1", input={"skill": "ticket"}),),
    )
    now = datetime.now(UTC)
    return DatasetVersion(
        id="d1-v1", dataset_id="d1", dataset_name="d1", dataset_description="",
        version=1, status=DatasetVersionStatus.PUBLISHED, cases=(case,),
        published_at=now, created_at=now, updated_at=now,
    )


def _run(dataset):
    snapshot = RunSnapshot(
        dataset=dataset,
        target=TargetSnapshot(
            ref=TargetRef(
                platform_id="test", target_type=TargetType.AGENT,
                external_target_id="ticket-agent", external_version_id="v1",
            ),
            display_name="ticket", adapter_type="http", adapter_version="1",
        ),
        evaluator_specs=EVALUATORS,
        primary_evaluator_ids=tuple(item.id for item in EVALUATORS),
        metric_plan=MetricPlan(),
        gate_spec=GateSpec(),
    )
    return Run(snapshot=snapshot, status=RunStatus.RUNNING, started_at=datetime.now(UTC))


def _event_file(root, project="p1", session="s1", name="trace.jsonl"):
    directory = root / project / session
    directory.mkdir(parents=True, exist_ok=True)
    return directory / name


def _write(path, events):
    with open(path, "a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def _setup(tmp_path):
    repo = SQLiteRepository(tmp_path / "receiver.db")
    dataset = _dataset()
    run = _run(dataset)
    repo.save_run(run)
    repo.put_pending_trace(run.id, "c1", "inv-1", TRACE_ID)
    receiver = TraceSdkFileReceiver(tmp_path / "sdk-out", repo)
    return repo, run, receiver


def _full_events(with_metadata=False):
    """一次完整 Agent 运行的事件流。桥接契约：TraceEvent metadata 带 turn id
    与 final_state（state 的评测数据源）。"""
    meta = {
        "agentgate.run.id": "PLACEHOLDER", "agentgate.case.id": "c1",
        "agentgate.turn.id": "t1",
        "agentgate.final_state.json": '{"status": "pending_review", "approved": false}',
    } if with_metadata else {
        "agentgate.turn.id": "t1",
        "agentgate.final_state.json": '{"status": "pending_review", "approved": false}',
    }
    return [
        {
            "event_type": "span", "trace_id": TRACE_ID, "span_id": "sp-root",
            "name": "TicketAgent", "span_type": "agent",
            "started_at": "2026-09-04T03:00:00Z", "duration_ms": 50,
            "metadata": meta if with_metadata else {},
        },
        {
            "event_type": "span", "trace_id": TRACE_ID, "span_id": "sp-tool",
            "parent_span_id": "sp-root", "name": "review_ticket", "span_type": "tool",
            "started_at": "2026-09-04T03:00:00.02Z", "duration_ms": 30,
            "metadata": meta if with_metadata else {},
        },
        {
            "event_type": "trace", "event_id": "ev-terminal", "trace_id": TRACE_ID,
            "status": "success", "output": {"status": "pending_review"},
            "metadata": meta,
        },
    ]


def test_receiver_poll_to_complete_via_pending_correlation(tmp_path):
    """验收 #34+36：pending 关联 → trace_complete → canonical Trace 收敛 COMPLETE。"""
    repo, run, receiver = _setup(tmp_path)
    events = _full_events()
    _write(_event_file(tmp_path / "sdk-out"), events)

    assert receiver.poll_once() == 1
    trace = repo.get_trace(run.id, "c1")
    assert trace is not None
    assert trace.status.value == "complete"
    assert [s.name for s in trace.spans] == [
        "TicketAgent", "review_ticket", "agent.complete",
    ]
    assert trace.final_output == {"status": "pending_review"}
    assert trace.final_state == {"status": "pending_review", "approved": False}


def test_receiver_idempotent_across_repeated_polls(tmp_path):
    """验收 #35：重复轮询不产生重复 span / 新批次。"""
    repo, run, receiver = _setup(tmp_path)
    _write(_event_file(tmp_path / "sdk-out"), _full_events())

    assert receiver.poll_once() == 1
    assert receiver.poll_once() == 0  # offset 已推进，无新内容

    trace = repo.get_trace(run.id, "c1")
    assert len(trace.spans) == 3

    # 全量重放同文件（模拟重复投递）：offset 归零重读 → 批次哈希/身份去重兜底
    receiver._offsets.clear()
    receiver.poll_once()
    trace = repo.get_trace(run.id, "c1")
    assert len(trace.spans) == 3
    assert trace.conflict_count == 0


def test_receiver_half_line_tolerance(tmp_path):
    """验收 #35：半行留待下轮，补齐换行后摄取。"""
    repo, run, receiver = _setup(tmp_path)
    path = _event_file(tmp_path / "sdk-out")

    full = json.dumps(_full_events()[0], ensure_ascii=False)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(full + "\n")
        handle.write(json.dumps(_full_events()[1])[:30])  # 半行
    assert receiver.poll_once() == 1
    assert repo.get_trace(run.id, "c1") is None or len(
        repo.get_trace(run.id, "c1").spans
    ) == 1

    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(_full_events()[1])[30:] + "\n")
        handle.write(json.dumps(_full_events()[2]) + "\n")
    assert receiver.poll_once() == 1

    trace = repo.get_trace(run.id, "c1")
    assert trace.status.value == "complete"
    assert len(trace.spans) == 3


def test_receiver_incremental_appended_events(tmp_path):
    """同文件追加事件（Agent 分批 flush）：两轮轮询合并为一个 canonical Trace。"""
    repo, run, receiver = _setup(tmp_path)
    path = _event_file(tmp_path / "sdk-out")
    events = _full_events()

    _write(path, events[:1])
    assert receiver.poll_once() == 1
    assert repo.get_trace(run.id, "c1").status.value == "collecting"

    _write(path, events[1:])
    assert receiver.poll_once() == 1
    trace = repo.get_trace(run.id, "c1")
    assert trace.status.value == "complete"
    assert len(trace.spans) == 3


def test_receiver_rejects_unmatched_trace_events(tmp_path):
    """无 pending 关联且无 metadata → 事件拒绝，不落孤儿数据。"""
    repo = SQLiteRepository(tmp_path / "orphan.db")
    receiver = TraceSdkFileReceiver(tmp_path / "sdk-out", repo)
    _write(_event_file(tmp_path / "sdk-out"), [
        {"event_type": "span", "trace_id": "ff" * 16, "span_id": "s1",
         "name": "orphan", "span_type": "tool"},
    ])
    receiver.poll_once()
    assert repo.list_runs() == []
    assert repo.get_trace("no-run", "c1") is None


def test_receiver_with_metadata_correlation(tmp_path):
    """metadata 携带完整关联（桥接主路径）：不依赖 pending 表。"""
    repo, run, receiver = _setup(tmp_path)
    events = _full_events(with_metadata=True)
    for event in events:
        event["metadata"] = {
            "agentgate.run.id": run.id, "agentgate.case.id": "c1",
            "agentgate.invocation.id": "inv-1", "agentgate.turn.id": "t1",
        }
    _write(_event_file(tmp_path / "sdk-out"), events)
    receiver.poll_once()
    trace = repo.get_trace(run.id, "c1")
    assert trace.status.value == "complete"


def test_receiver_ignores_missing_root(tmp_path):
    receiver = TraceSdkFileReceiver(tmp_path / "nonexistent", SQLiteRepository(
        tmp_path / "empty.db"
    ))
    assert receiver.poll_once() == 0
