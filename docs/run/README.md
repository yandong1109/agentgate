# Run

The Run capability owns deterministic execution mechanics:

```text
run/
├── engine.py
├── process_manager.py
├── retry.py
├── manifest.py
├── artifacts.py
└── target_protocol.py
```

Complete Run lifecycle orchestration belongs in `application/run_management.py`.
Concrete Agent integrations belong in `integrations/targets/`, and Celery background
submission belongs in `integrations/job_dispatchers/`.

Detailed plans:

- [External target integration](external-target-plan.md)
- [HTTP Target and OTel correlation](http-target-short-term-plan.md) — historical
  implementation record; the OTLP correlation scheme is superseded by the trace-sdk path
- [Instrumented Demo Agent](demo-agent-plan.md)
- [trace-sdk integration (trace generation/reporting switch)](../trace/trace-sdk-integration-plan.md)

The current branch implements `TargetSnapshot`, Python and HTTP execution adapters,
W3C `traceparent` propagation, pending Trace correlation, Trace waiting, regression-set
execution, and single-Case rerun. Trace generation/reporting on the Agent side is
switching from OTel/OTLP to the trace-sdk event model (file/Redis pull ingestion on the
AgentGate side; the OTLP channel is retained during the gray-release window). Target
catalog/discovery, process and trace-only adapters, production credential management,
retry/cancellation scheduling, and OTLP/gRPC remain deferred. Plan file maps are not
authoritative.
