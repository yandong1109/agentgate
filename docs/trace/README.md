# Trace

The current Trace implementation owns bounded OTLP ingestion, trace-sdk event ingestion,
canonical semantic conversion, deterministic reconstruction, and lifecycle protection:

```text
trace/
├── models.py
├── receivers/otlp_http.py        # OTLP 通道（过渡期保留，存量 OTel 目标）
├── receivers/trace_sdk.py        # trace-sdk 事件通道（新：file / Redis 拉取）
├── normalizer.py                 # OTLP 分支 + trace-sdk 事件归一化分支
├── ordering.py
├── merge.py
├── completeness.py
└── service.py
```

`POST /v1/traces` accepts OTLP/HTTP JSON and protobuf, including gzip (**transitional
channel**: retained during the trace-sdk gray-release window for existing OTel targets).
The trace-sdk channel is pull-based: `receivers/trace_sdk.py` pulls events from the SDK
file backend (same-machine default) or Redis Stream (independent consumer group). Both
channels converge on the same NormalizedSpan pipeline: the normalizer produces
`TraceBatch`, the service validates Run/Case/Turn/Target correlation, and SQLite
persists spans, semantic signals, conflicts, and immutable canonical Trace revisions.
`GET /api/runs/{run_id}/traces/{case_id}` returns the latest canonical Trace.

Domain Trace models and invariants remain in `domain/`; persistence remains in
`storage/`. Vendor importers and OTLP/gRPC remain future observability integrations.

The [ingestion plan](ingestion-plan.md) records the implemented contract and explicitly
lists the remaining cross-module work. Its pre-refactor file map is not authoritative.
The [trace-sdk integration plan](trace-sdk-integration-plan.md) specifies the new
trace generation/reporting path (event model, bridge correlation, receiving modes,
mapping table) and the gray-release schedule.
