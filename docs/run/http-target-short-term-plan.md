# HTTP Target Adapter + OTel Trace Correlation — Short-Term Plan

> [!IMPORTANT]
> **Trace 传输方式变更（2026-09）**：本文件描述的 OTLP 关联方案已由 trace-sdk
> 路径（事件模型，file/Redis 传输）接替。**本文保留为历史实施记录**：其大部分
> 条目已实施完毕且仍在生产运行（灰度窗口期 OTLP 通道保留）；尚未实施的条目不再
> 按本文件推进。新路径设计见
> [trace-sdk-integration-plan](../trace/trace-sdk-integration-plan.md)；HTTP 适配器
> 本身（invoke 契约、头部、错误语义）不受切换影响。
>
> Status: implemented and verified on `codex/trace-ingestion` (2026-08-25).
> Modification level: **M** (new target domain contract + HTTP adapter + RunEngine
> refactor + OTel trace-correlation mechanism; no Architecture Rule is changed).
>
> The implemented Trace module now exceeds this short-term plan's original minimum:
> OTLP/HTTP JSON and protobuf, gzip, bounded normalization, merge/deduplication,
> completeness, conflicts, and immutable revisions are available. OTLP/gRPC remains
> deferred. See `docs/trace/ingestion-plan.md`.
>
> Design source: `docs/run/external-target-plan.md` (behavior and acceptance criteria
> remain authoritative). This document scopes a short-term implementation subset and
> specifies the OTel trace-correlation mechanism that `external-target-plan.md` left to
> the trace module. The full ingestion plan (`docs/trace/ingestion-plan.md`) still owns
> merge, deduplication, ordering, and completeness semantics; this plan implements only
> the minimal correlation subset required for the HTTP + OTel path.
>
> Target branch: `integration/p1` (short-term). Path migration to `refactor-1` is tracked
> in §11.

## 1. Goal and User Decisions

### Goal

Make AgentGate evaluate a **real** external Agent through a real HTTP API against a real
authored Dataset/Case, with the Agent exporting OpenTelemetry traces over OTLP, and
produce a real canonical Trace + evaluation Result + report — replacing the loan demo's
hard-coded `name="loan-agent"` synthetic-trace path for this integration.

### User-confirmed decisions

1. **Agent form**: an HTTP API service built on the LangChain framework. AgentGate calls
   the Agent's HTTP API and does **not** depend on the LangChain SDK. LangChain is an
   internal framework of the Agent service. Short-term deliverable is `run/targets/http.py`;
   a dedicated `run/external/langchain.py` framework adapter is deferred.
2. **Trace**: the Agent uses the OpenTelemetry SDK to export traces, sent over OTLP
   (HTTP/JSON) to AgentGate's existing `POST /v1/traces` receiver. Correlation uses the
   **W3C Trace Context `traceparent` header** (trace_id propagation), not Agent-stamped
   `agentgate.*` span attributes as the primary mechanism.

### End-to-end acceptance shape

```text
author/publish a real Dataset + Case
  -> launch an HTTP target (endpoint + TargetRef + credential_ref)
  -> RunEngine builds TargetSnapshot + per-Case traceparent + pending mapping
  -> HttpTargetAdapter calls the Agent HTTP API with traceparent + X-AgentGate-* headers
  -> Agent inherits trace context, runs, returns output/state/trace_id
  -> Agent OTel SDK exports OTLP to /v1/traces
  -> receiver resolves trace_id -> run_id/case_id via pending mapping
  -> normalizer maps OpenInference/gen_ai spans -> canonical Trace
  -> RunEngine awaits Trace, then evaluates
  -> real Trace + Result + Gate + report visible; loan demo non-regression preserved
```

## 2. Scope (do / defer, mapped to external-target-plan §Scope)

external-target-plan §Scope lists 8 items. This increment's mapping:

| # | external-target-plan item | This plan | Note |
| --- | --- | --- | --- |
| 1 | Target terminology and immutable domain contracts | **DO (trimmed)** | `TargetType`, `TargetRef`, enhanced `TargetSnapshot`, `TargetExecutionRequest`, `TargetExecutionResult`. `TargetDescriptor`/`ToolDescriptor`/`SkillDescriptor` deferred. |
| 2 | A metadata/version catalog adapter | **SPLIT** | Local target **registry / listing / routing** is **DO** (§A): the service holds a registered-target list (loan demo + langchain HTTP sample), `versions()` lists them, `launch` routes by `target_id`. The full catalog adapter that queries an external platform API (`list_targets`/`list_versions`/`get_descriptor`) stays **DEFER**. |
| 3 | A target execution adapter | **DO** | `TargetExecutionAdapter` protocol + HTTP adapter + Python adapter. |
| 4 | Demo and Python adapters using the new contracts | **DO (partial)** | `PythonFunctionTarget` adapted to the new contract; LoanAgent wrapped (non-regression). A dedicated `run/targets/demo.py` catalog adapter deferred. |
| 5 | An HTTP adapter tested against a fake external platform | **DO** | `HttpTargetAdapter` + a fake HTTP Agent test fixture (OpenInference-style OTLP export) + a runnable **LangChain HTTP agent sample service** under `demo/` (§B) for manual and Web end-to-end runs. |
| 6 | A trace-only adapter | **DEFER** | `run/targets/trace_only.py` stays an empty boundary. |
| 7 | Explicit Run/Case/Turn/idempotency/Trace correlation data | **DO** | Correlation by `trace_id` (pending mapping) + W3C `traceparent`; the core design focus (§4). |
| 8 | Target-related validation, errors, tests, documentation | **DO (subset)** | Error taxonomy subset used on the HTTP path; tests; this document; registered-target **listing API** for Web/CLI (§A, §C). Full catalog query API and `TargetDescriptor` persistence deferred. |

### Non-Goals (this increment)

- Agent lifecycle management (start/stop/scale the Agent service) — invariant #6; the
  Agent is an external asset.
- LangChain/autogen/openai_agents framework SDK adapters (`run/external/*.py`).
- Full catalog adapter that queries an external platform API
  (`list_targets`/`list_versions`/`get_descriptor`). Local target **registration / listing /
  routing** is in scope (§A); the registry is local configuration, not external-platform
  discovery.
- Full `TargetDescriptor`/`ToolDescriptor`/`SkillDescriptor` metadata (Prompt/tools/skills
  schema) — short-term Target only needs `ref` + endpoint + `credential_ref`.
- Production credential vault — POC uses an environment-variable credential resolver.
- Process adapter, trace-only adapter.
- OTLP/gRPC remains outside this increment. OTLP/HTTP merge, deduplication,
  completeness, and protobuf support have since been delivered by
  `docs/trace/ingestion-plan.md`.
- Target CRUD/management Web screens. Target **selection** in the launch UI is in scope
  (§C); creating/editing/publishing targets from the Web is not.
- Full `ExecutionPolicy` model — short-term uses RunEngine parameters with POC defaults.

### Invariants respected (checked against AGENTS.md §2)

- #1 `domain/` holds immutable data semantics only — target domain models carry no I/O.
- #2 Run owns orchestration (invocation identity, trace-wait policy); the adapter is a
  transport, not an orchestrator.
- #4 Trace adapter (normalizer) normalizes provider OTel data before evaluators consume.
- #5 Result aggregates; evaluators consume the canonical Trace only.
- #6 External Agent is an external asset; AgentGate does not manage its lifecycle.
- #9 `trace_timeout` is a Run/execution error with an explicit incomplete-trace policy,
  never an evaluator FAIL.
- #15 `credential_ref` is an opaque id; secrets never enter domain models, Trace, logs,
  or exceptions.

## 3. Current State and Gap (mapped to external-target-plan §Current State and Gap)

| Gap from external-target-plan (lines 50-63) | This plan |
| --- | --- |
| `TargetSnapshot` has no Target type or external object/version identity | **Fix**: enhanced `TargetSnapshot` with `ref: TargetRef` + `adapter_type`/`adapter_version`/`invocation_config`/`credential_ref`. |
| `RunEngine` hard-codes `name="loan-agent"` | **Fix**: RunEngine receives a `TargetSnapshot` + adapter; no hard-coded identity. |
| target version passed separately from the target object and snapshot | **Fix**: version lives inside `TargetRef`/`TargetSnapshot`; no separate version string. |
| `run/targets/base.py`, `http.py`, `process.py`, `python_fn.py`, `trace_only.py` empty | **Fix** `base.py`/`http.py`/`python_fn.py`; `process.py`/`trace_only.py` remain deferred. |
| no adapter for listing Agent/Skill objects or versions | **Defer** (catalog). |
| no normalized metadata contract for Dataset generation / Skill analysis | **Defer** (`TargetDescriptor`). |
| no request/response contract for invoking an external target | **Fix**: `TargetExecutionRequest`/`TargetExecutionResult`. |
| credentials/endpoint/timeout/retry/cancellation/idempotency not modeled | **Partial fix**: request carries `invocation_id`/`idempotency_key`/`timeout_seconds`/`traceparent`; `credential_ref` modeled; endpoint in `invocation_config`. Retry/cancellation deferred to Run/scheduler policy. |
| Trace correlation assumes the target directly returns a canonical Trace | **Fix**: HTTP adapter returns `trace_id` correlation; OTLP arrives separately; RunEngine awaits. |
| Demo provider and production target integration boundaries mixed | **Fix**: demo path goes through the same `TargetExecutionAdapter` contract (via `PythonFunctionTarget`); no special-case branch in RunEngine. |

### Additional gaps discovered before implementation (now resolved)

- The original `trace/normalizer.py` keyed traces by legacy correlation span attributes
  and assigned placeholder identities when absent. A generic
  LangChain Agent (OpenInference instrumentation) does **not** stamp `agentgate.*`
  attributes, so correlation by span attributes fails. **Fix**: correlation-by-`trace_id`
  pending-mapping resolver passed into the normalizer (§4, §8); unresolved spans are now
  rejected rather than assigned placeholders.
- The original normalizer mapped span kind only via `agentgate.kind`; it did not recognize
  OpenInference `openinference.span.kind` or OTel GenAI `gen_ai.*` attributes. LangChain
  spans would collapse to `SpanKind.EVENT`. **Fix**: add OpenInference/GenAI kind rules (§8).
- The original repository had no pending-correlation surface and the receiver had no
  `trace_id → run_id/case_id` lookup.
  **Fix**: repository gains `put_pending_trace`/`get_pending_trace`; receiver builds a
  resolver and passes it to the normalizer (§4, §6, §9).
- The original control-plane service instantiated `LoanAgent` directly and passed
  it to `engine.run` as a `Target` object + separate `version` string. **Fix**: unify on
  `TargetSnapshot` + `TargetExecutionAdapter` (§7).

## 4. Trace Correlation Timing Design

### Seven-step timing

```text
1. RunEngine (per Case) generates:
     invocation_id      = uuid4
     idempotency_key    = stable per (run_id, case_id, attempt)  [uuid4 on first attempt]
     trace_id           = uuid4().hex           (32 hex chars, W3C trace id)
     parent_span_id     = uuid4().hex[:16]      (16 hex chars, W3C span id)
     traceparent        = "00-{trace_id}-{parent_span_id}-01"   (W3C Trace Context)
2. RunEngine records a pending mapping in the repository:
     put_pending_trace(run_id, case_id, invocation_id, trace_id)
3. RunEngine builds TargetExecutionRequest (carries traceparent + run/case/turn ids +
     idempotency_key + target snapshot + input + state + timeout_seconds) and calls
     adapter.execute(request).
4. HttpTargetAdapter:
   - resolves credential_ref via CredentialResolver (env-var POC) -> Authorization header
     (secret stays in process memory only)
   - sends HTTP POST to Agent endpoint with headers:
       traceparent, baggage?(none POC), Idempotency-Key,
       X-AgentGate-Run-Id, X-AgentGate-Case-Id, X-AgentGate-Turn-Id?(when present)
     and body: {invocation_id, idempotency_key, target{type,id,version_id},
                run_id, case_id, turn_id, input, state}
   - validates status code, content-type, response shape; maps errors to taxonomy (§6)
   - returns TargetExecutionResult{ invocation_id, external_execution_id, output,
       final_state, inline_trace=None, trace_id=<from response or traceparent's>,
       completed_at }
5. Agent (LangChain + OTel SDK) inherits the trace context from the traceparent header,
   creates spans under trace_id, and exports OTLP/HTTP JSON to POST /v1/traces.
6. Receiver (otlp_http.ingest_otlp_http_json) + normalizer:
   - normalizer groups spans by trace_id
   - run_id/case_id resolution priority:
       (a) agentgate.run_id / agentgate.case_id span attributes (if Agent cooperates)
       (b) pending mapping looked up by trace_id  (resolver built from repository)
       (c) reject the span when no valid correlation exists
   - kind resolution priority (§8): agentgate.kind > openinference.span.kind >
       gen_ai.* heuristic > EVENT default
   - receiver delegates the validated `TraceBatch` to the ingestion service, which
     persists evidence and reconstructs the canonical Trace by `(run_id, case_id)`
7. RunEngine awaits Trace:
   - if result.inline_trace is present (demo/python adapter): use directly, no wait.
   - else poll repository.get_trace(run_id, case_id) every poll_interval (POC 0.5s)
     until present or trace_wait_seconds elapses (POC 30s).
   - on timeout: build a degraded Trace (see below), record a trace_timeout warning,
     and proceed to evaluate under the incomplete-trace policy.
```

### Answers to the four required questions

**Q1 — Where is `trace_id` generated? Format of `traceparent`?**

Generated in **RunEngine** (the orchestration owner; invariant #2). RunEngine decides
invocation identity and correlation context and passes them inside
`TargetExecutionRequest.traceparent`. The adapter is a transport that propagates the
header; it does **not** invent identity. (This matches the request contract in
external-target-plan §TargetExecutionRequest, which carries `traceparent` as a field.)

`traceparent` follows W3C Trace Context:
`<version>-<trace_id>-<parent_span_id>-<flags>` = `00-<32 hex trace_id>-<16 hex
parent_span_id>-<2 hex flags>`, e.g. `00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01`.

**Q2 — Where is the pending mapping stored? POC limitations?**

In the **repository** (a new SQLite table `pending_trace_correlation`), **not** in
RunEngine memory. The receiver is a separate FastAPI request handler
(`POST /v1/traces`) and cannot see RunEngine's process-local state; both share the same
repository (the app's SQLite singleton), so the repository is the only viable shared
surface.

Repository surface (added to the `AgentGateRepository` Protocol):

```text
put_pending_trace(run_id, case_id, invocation_id, trace_id) -> None   # idempotent upsert
get_pending_trace(trace_id) -> PendingTraceCorrelation | None         # non-destructive
```

POC limitations to state explicitly:
- Lookup is **non-destructive**; OTLP may arrive in multiple batches, so the mapping is
  not consumed on first batch.
- Cleanup is **deferred**: entries remain after the Run. A run-completion sweep or TTL job
  is owned by `docs/trace/ingestion-plan.md`; the short-term table will grow slowly and
  is acceptable for a POC. A follow-up cleanup task is noted in §12.
- The mapping is per-`(run_id, case_id, trace_id)`; a one-Case-one-invocation-one-trace
  assumption holds for the POC. Multi-turn and multi-trace merge is ingestion-plan scope.

**Q3 — "Wait for trace" mechanism? Degraded fallback semantics?**

Polling: RunEngine polls `repository.get_trace(run_id, case_id)` every `poll_interval`
(POC **0.5s**) up to `trace_wait_seconds` (POC **30s**). Both are RunEngine parameters
(POC defaults; a formal `ExecutionPolicy` model is deferred).

Degraded fallback (the explicit incomplete-trace policy; external-target-plan §Trace
Correlation "timeout → apply explicit incomplete-trace policy" and "Do not evaluate an
empty synthetic Trace as if complete telemetry existed"):

- Construct a **degraded Trace**: `Trace(run_id, case_id, spans=(), turns=(),
  final_output=result.output, final_state=result.final_state)`, marked incomplete
  (a `degraded=True`/`incomplete=True` indicator — see §5; alternatively a Run-level
  warning, chosen at implementation to avoid widening the canonical Trace contract
  unnecessarily).
- Span-dependent evaluators (routing, required-tool, forbidden-tool, tool-arguments)
  report **N/A** (`outcome=not_applicable`, `score=null`) because there are no spans.
- Output/state-dependent evaluators (final-state, final-output, policy-compliance)
  **do run** on `final_output`/`final_state` from the HTTP response.
- A `trace_timeout` warning/error is recorded on the Run (Run/execution error, invariant
  #9); it is **not** an evaluator ERROR and **not** an Agent FAIL.
- The degraded Trace is an orchestration placeholder carrying no spans; it is explicitly
  **not** a normalized provider trace. Real normalization always lives in `trace/`
  (invariant #4). Implementation must choose the lightest representation that still lets
  evaluators distinguish "no spans (degraded)" from "spans present".

**Q4 — Does the normalizer support OTel GenAI / OpenInference? What to add?**

**No.** Current `normalize_otlp_json` maps kind only via `agentgate.kind` and defaults
to `SpanKind.EVENT`. It does not recognize OpenInference `openinference.span.kind` or
OTel GenAI `gen_ai.*` attributes, so LangChain-exported spans collapse to `EVENT`.

LangChain's standard OTel path is the `openinference-instrumentation-langchain`
instrumentation (hooks `langchain-core`), which emits ordinary OTel spans with
`openinference.span.kind` (LLM/TOOL/AGENT/CHAIN/RETRIEVER/GUARDRAIL/...) and `llm.*` /
`tool.*` / `agent.name` attributes, exported via standard OTLP. Some instrumentations also
emit `gen_ai.*` (OTel GenAI semantic conventions: `gen_ai.system`, `gen_ai.request.model`,
`gen_ai.usage.*`, `gen_ai.prompt.*`, `gen_ai.completion.*`, `gen_ai.tool.name`) for
compatibility.

Rules to add to `trace/normalizer.py` (priority order):

1. `agentgate.kind` (AgentGate-native, explicit) → use directly (highest priority; the
   Agent may cooperate by stamping it).
2. `openinference.span.kind` → map: `LLM`→`AGENT`, `AGENT`→`AGENT`, `CHAIN`→`AGENT`,
   `TOOL`→`TOOL`, `RETRIEVER`→`TOOL`, `GUARDRAIL`/`EMBEDDING`/`RERANKER`→`EVENT`.
3. `gen_ai.*` heuristic: a span carrying `gen_ai.system` (LLM call) → `AGENT`; a span
   carrying `gen_ai.tool.name` or `tool.name` → `TOOL`.
4. default → `EVENT`.

run_id/case_id resolution priority (also added): `agentgate.run_id`/`agentgate.case_id`
span attrs → pending mapping by `trace_id` (via the new `correlation_resolver` callback
parameter) → placeholder.

Implementation note: the **actual** attribute scheme exported by the user's real Agent is
determined at wiring time. The adapter must adapt to whatever the Agent emits; the
normalizer must add the matching rules. This plan assumes standard OTel GenAI / OpenInference
attributes (the user-confirmed assumption); if the Agent emits a non-standard scheme, the
implementer extends the normalizer rules and records the decision. Research notes on the
attribute schemes are stored in `.tavily/langchain-otel-openinference.md`.

## 5. Domain Model Increment (`src/agentgate/domain/target.py`)

Add `src/agentgate/domain/target.py`. Field definitions follow external-target-plan
§Domain Model (lines 266-400). Trimmed fields are marked.

```python
class TargetType(StrEnum):
    AGENT = "agent"
    SKILL = "skill"          # POC uses AGENT only; SKILL reserved


class TargetRef(DomainModel):
    platform_id: str
    target_type: TargetType
    external_target_id: str
    external_version_id: str
```

All four fields required and non-empty; the tuple is the external identity (external-target-plan rule 3).

```python
class TargetSnapshot(DomainModel):           # MOVED from domain/run.py and enhanced
    ref: TargetRef
    display_name: str
    adapter_type: str
    adapter_version: str
    descriptor_sha256: str                    # "" when no descriptor (short-term: no catalog)
    invocation_config: FrozenJsonObject      # endpoint, headers, etc. (NO secrets)
    credential_ref: str | None               # opaque id; NEVER a secret value
    captured_at: datetime
    content_sha256: str
```

Rules (external-target-plan §TargetSnapshot): no plaintext credential; no mutable
endpoint-discovery result that cannot be reproduced; adapter type/version mandatory;
`invocation_config` contains normalized non-secret configuration; content hash covers
every field except itself; RunSnapshot embeds the complete TargetSnapshot.

**Trimmed vs. external-target-plan**: `TargetDescriptor`, `ToolDescriptor`,
`SkillDescriptor` are deferred (no catalog adapter short-term). `descriptor_sha256` is
kept as `""` so the field exists when the catalog arrives.

```python
class TargetExecutionRequest(DomainModel):
    invocation_id: str
    idempotency_key: str
    run_id: str
    case_id: str
    turn_id: str | None                      # None until multi-turn
    target: TargetSnapshot
    input: FrozenJsonObject
    state: FrozenJsonObject
    timeout_seconds: float
    traceparent: str                         # W3C Trace Context, generated by RunEngine
    baggage: str | None                     # None POC


class TargetExecutionResult(DomainModel):
    invocation_id: str
    external_execution_id: str | None
    output: FrozenJsonValue
    final_state: FrozenJsonObject
    inline_trace: Trace | None               # demo/python adapters; None for HTTP
    trace_id: str | None                     # correlation reference for HTTP
    completed_at: datetime
```

Do **not** name this object `Result` (external-target-plan rule; `Result` belongs to
evaluator output).

### Runtime-only credential type (NOT a domain model; lives in `run/targets/base.py`)

A `ResolvedCredential` runtime object holds the resolved secret in process memory and is
**never** a Pydantic domain model, never persisted, never logged, never put into Trace
attributes or exceptions (external-target-plan §CredentialResolver + Security rules). The
`CredentialResolver` Protocol is defined in `run/targets/base.py`; the POC implementation
`EnvCredentialResolver` reads an environment variable named by `credential_ref`.

### Degraded-trace marker

Implementation chooses the lightest of: (a) a Run-level `trace_warnings` list carrying
`trace_timeout`, or (b) a non-persisted flag on the in-memory Trace handed to evaluators.
Either way, span-dependent evaluators must observe "no spans" and report N/A. This must
not widen the persisted canonical `Trace` contract; a formal completeness lifecycle is
owned by `docs/trace/ingestion-plan.md`.

### `domain/__init__.py` and `domain/run.py` changes

- `domain/run.py`: remove the old minimal `TargetSnapshot` (name/version/provider/config).
- `domain/__init__.py`: re-export `TargetSnapshot` (and new target contracts) from
  `domain/target.py`. external-target-plan: "The old TargetSnapshot definition is moved,
  not retained as a compatibility duplicate."
- `RunSnapshot.target` type becomes `domain.target.TargetSnapshot`; the content hash now
  covers the richer snapshot (acceptance #4: changing target version / adapter version /
  invocation config changes RunSnapshot hash).

## 6. Adapter Changes

### `run/targets/base.py` (Protocol surface; runtime credential types)

- `TargetExecutionAdapter(Protocol)`: `adapter_type`, `adapter_version`, and
  `execute(request: TargetExecutionRequest) -> TargetExecutionResult`.
- `CredentialResolver(Protocol)`: `resolve(credential_ref) -> ResolvedCredential`.
- `ResolvedCredential`: runtime holder for the secret (e.g. `Authorization` header value);
  not a domain model; never serialized.
- `TargetIntegrationError` taxonomy base + the subset used on the HTTP path
  (`target_not_found`, `unauthorized`, `invalid_configuration`, `rate_limited`,
  `timeout`, `unavailable`, `rejected`, `protocol_error`, `trace_timeout`). Full
  `version_not_found` overlaps with `target_not_found` when no catalog resolves versions;
  both are declared, the catalog-relevant branches are exercised later.

### `run/targets/python_fn.py` (adapt; non-regression for loan demo)

Implements `TargetExecutionAdapter`. Wraps a registered callable. For the loan demo the
callable is `LoanAgent.execute`-shaped: it already returns a canonical `Trace`
(synthetic, with spans). The adapter translates
`TargetExecutionRequest` → call → `TargetExecutionResult` with
`inline_trace=<returned Trace>`, `output=trace.final_output`,
`final_state=trace.final_state`, `trace_id=<trace's trace_id>`. RunEngine consumes
`inline_trace` directly (no OTLP wait). LoanAgent stays under `demo/`; only the adapter
glue changes.

### `run/targets/http.py` (implement; the core short-term deliverable)

`HttpTargetAdapter(TargetExecutionAdapter)`:

- constructed with `endpoint` (from `invocation_config`), `CredentialResolver`, an HTTP
  client (stdlib `urllib` or `httpx` if already a dependency), and `adapter_type="http"`.
- `execute(request)`:
  1. resolve `credential_ref` → `ResolvedCredential` → `Authorization` header (in memory
     only; never returned in `TargetExecutionResult`, never logged).
  2. POST to `endpoint` with headers `traceparent`, `Idempotency-Key`,
     `X-AgentGate-Run-Id`, `X-AgentGate-Case-Id`, `X-AgentGate-Turn-Id` (when present),
     `Authorization`, `Content-Type: application/json`; body per external-target-plan
     §HTTP Adapter initial request.
  3. enforce `request.timeout_seconds` (remaining deadline).
  4. validate HTTP status (200/4xx/5xx → taxonomy), content-type (`application/json`),
     and response shape (must contain `output`, `final_state`, optionally
     `external_execution_id` and `trace_id`).
  5. return `TargetExecutionResult`. `trace_id` comes from the response if echoed,
     otherwise from `request.traceparent`'s trace_id (the one RunEngine generated).
  6. Does **not** parse telemetry as evaluator evidence (external-target-plan rule).
- Sanitize public errors; keep full technical detail in protected logs only; redact
  `Authorization`, cookies, tokens (Security rules). Never expose the resolved secret in
  any error/Trace/log (invariant #15).

### `run/core.py` (RunEngine refactor)

Signature changes from `run(dataset, target, target_version, provider, evaluators)` to:

```text
run(dataset_version, target_snapshot, adapter, evaluators,
    trace_wait_seconds=30.0, trace_poll_interval_seconds=0.5)
```

- remove hard-coded `name="loan-agent"`; build `RunSnapshot` from the passed
  `target_snapshot`.
- the old `Target` Protocol and `PythonFunctionTarget` class move to `run/targets/`
  (`PythonFunctionTarget` becomes the `python_fn` adapter; `Target` Protocol is replaced
  by `TargetExecutionAdapter`).
- `LocalScheduler`/`ExternalSchedulerAdapter`: the local synchronous path becomes a thin
  delegation to `adapter.execute(request)`; the external scheduler boundary is retained
  but the short-term local path needs no separate scheduler object. Keep the boundary
  symbol so the external-scheduler future is not blocked, but RunEngine may call the
  adapter directly for the POC.
- per-Case loop (§4 seven-step): generate invocation identity + traceparent; record pending
  mapping; build request; `result = adapter.execute(request)`; resolve Trace
  (inline or await OTLP); evaluate.
- error handling: map adapter exceptions to the `TargetIntegrationError` taxonomy; on
  `trace_timeout` apply the degraded fallback (§4 Q3); save_run(failed) for non-retryable
  execution errors; **never** convert an invocation error into an evaluator FAIL
  (invariant #9; external-target-plan rule 9). Identity/configuration errors are rejected
  before execution when possible (external-target-plan rule, acceptance).
- validate dataset is `PUBLISHED` and the evaluation plan (unchanged behavior).

### `demo/loan.py`

Minimal change: `LoanAgent` keeps returning a canonical `Trace`; it is wrapped by the
`python_fn` adapter. No risky/fixed outcome change (acceptance #9).

## 7. Control Plane Changes

### `control_plane/service.py`

Unify on `TargetSnapshot` + `TargetExecutionAdapter`:

```text
launch_target(snapshot, adapter, dataset_id, dataset_version, evaluator_ids,
              trace_wait_seconds, trace_poll_interval_seconds) -> Run
```

- `launch(target_id, dataset_id, dataset_version, evaluator_ids)` — **signature-compatible**
  with the demo `version` param: loan version strings remain valid `target_id`s, so the
  existing CLI `agentgate evaluate --version ...`, `POST /api/evaluations`, and Web launch
  keep working (non-regression). Internally the first param is now a **target_id routed via
  the local target registry** (§A): a loan demo id builds a demo `TargetSnapshot`
  (`ref.platform_id="demo"`, `external_target_id="loan-agent"`,
  `external_version_id=version`, `adapter_type="python_fn"`) + a `PythonFunctionTarget`
  wrapping `LoanAgent`; a registered HTTP target id builds an HTTP `TargetSnapshot`
  (`adapter_type="http"`, `invocation_config`/`credential_ref` from the registry) +
  `HttpTargetAdapter(endpoint, EnvCredentialResolver())`; then `launch_target(...)` is
  called. On unknown `target_id` → `target_not_found`, rejected before execution.
- `versions()` becomes `list_targets()` (route `GET /api/versions` unchanged): returns the
  registry as `[{target_id, label, adapter_type, endpoint?, credential_ref?}]` so the Web
  selector is data-driven (§A, §C).
- `launch_http(target_ref, endpoint, credential_ref, dataset_id, dataset_version,
  evaluator_ids, timeout_seconds, trace_wait_seconds=30.0, ...)` — remains as the explicit
  programmatic HTTP entry that bypasses the registry for ad-hoc endpoints; used by
  `agentgate evaluate-http` CLI and `POST /api/evaluations/http`.
- Credential resolution: `EnvCredentialResolver` reads the environment variable named by
  `credential_ref` at execute time (in the adapter). The service never holds the secret.

### `server/application.py`

- `POST /api/evaluations` (demo): unchanged request/response (non-regression); internally
  now routes through `launch_target`.
- `POST /api/evaluations/http` (new): accepts `target_ref`, `endpoint`,
  `credential_ref` (env-var name), `dataset_id`, `dataset_version`, `evaluator_ids`,
  `timeout_seconds`; calls `service.launch_http(...)`. (The future unified `POST /api/runs`
  per external-target-plan §API Boundary merges these; tracked in §12.)
- `POST /v1/traces`: already passes `repository` to `ingest_otlp_http_json`; the receiver
  now also uses `repository.get_pending_trace` to build the correlation resolver (§8). No
  new route; the receiver signature gains a resolver-building step internally.

### `cli/`

- `agentgate evaluate --version ...` (demo): unchanged (non-regression).
- `agentgate evaluate-http --endpoint URL --target-id ID --version-id VID
  --credential-ref ENV_VAR_NAME [--platform-id ...] --dataset ID --dataset-version N
  [--evaluator-ids ...] [--timeout-seconds ...]`: new command calling
  `service.launch_http`. (Exact flag names finalized at implementation; the plan fixes the
  intent, not the CLI grammar.)

## 8. Normalizer Assessment (`trace/normalizer.py`)

### Current state

- Produces a bounded `TraceBatch` rather than one Trace per request.
- Resolves canonical dotted `agentgate.*` correlation, compatible legacy aliases, and
  pending `trace_id → run_id/case_id/invocation_id` mappings.
- Maps explicit AgentGate, OpenInference, and OTel `gen_ai.*` semantics to canonical
  span kinds, with generic EVENT as the final fallback.
- Rejects uncorrelated spans instead of assigning placeholder Run/Case identities.

### Implemented changes

1. **Kind resolution** with the priority in §4 Q4 (agentgate.kind > openinference.span.kind
   > gen_ai.* heuristic > EVENT). Mapping table in §4 Q4.
2. **run_id/case_id resolution** with priority in §4 step 6 (agentgate.* span attrs >
   pending mapping by `trace_id` > strict rejection).
3. New optional parameter:
   ```text
   correlation_resolver: Callable[[str], tuple[str, str] | None] | None = None
   ```
   When `agentgate.run_id`/`agentgate.case_id` are absent, the normalizer calls
   `correlation_resolver(trace_id)`; if it returns `(run_id, case_id)`, those are used.
   The resolver is built by the receiver from `repository.get_pending_trace` (§9). The
   normalizer stays pure (no direct repository dependency) — the receiver injects the
   resolver.
4. Preserve `agentgate.*` priority so a cooperating Agent (one that stamps
   `agentgate.*` attributes) still works without the pending mapping.

### Receiver change (`trace/receivers/otlp_http.py`)

`ingest_otlp_http_json(payload, repository)` builds a resolver closure over
`repository.get_pending_trace` and passes it to `normalize_otlp_json`. After
normalization, the Trace ingestion service validates and persists the accepted batch.
Uncorrelated spans are rejected and reported through partial-success counters; no
placeholder Trace is created.

## 9. File Change Map (trimmed from external-target-plan §Code Change Map)

Status labels: `[ADD]` create, `[MOD]` modify, `[KEEP]` reuse, `[DEFER]` reserved.

```text
src/agentgate/
├── domain/
│   ├── __init__.py                    [MOD] export target contracts; TargetSnapshot from target.py
│   ├── target.py                      [ADD] TargetType, TargetRef, TargetSnapshot (moved+enhanced),
│   │                                        TargetExecutionRequest, TargetExecutionResult
│   └── run.py                         [MOD] remove old TargetSnapshot; RunSnapshot.target -> target.TargetSnapshot
│
├── run/
│   ├── core.py                        [MOD] RunEngine.run(snapshot, adapter, ...); remove hard-coded
│   │                                        name; remove old Target Protocol + PythonFunctionTarget (move)
│   └── targets/
│       ├── __init__.py                [MOD] export adapter API
│       ├── base.py                    [MOD] TargetExecutionAdapter + CredentialResolver Protocols,
│       │                                    ResolvedCredential runtime type, error taxonomy base
│       ├── python_fn.py               [MOD] PythonFunctionTarget adapter (wraps callable -> result w/ inline_trace)
│       ├── http.py                    [MOD] HttpTargetAdapter (the core deliverable)
│       ├── process.py                 [DEFER] empty boundary
│       └── trace_only.py              [DEFER] empty boundary
│
├── control_plane/
│   └── service.py                     [MOD] launch_target core; local target registry (list + route by
│                                            target_id); launch (signature-compatible, routes via registry);
│                                            launch_http (explicit HTTP entry); EnvCredentialResolver wiring — see §A
│
├── server/
│   └── application.py                 [MOD] POST /api/evaluations/http (new); GET /api/versions returns the
│                                           multi-target registry listing; /v1/traces builds resolver
│
├── cli/                               [MOD] new evaluate-http command (file(s) per existing CLI structure)
│
├── trace/
│   ├── normalizer.py                  [MOD] correlation_resolver param + OpenInference/gen_ai kind rules
│   └── receivers/otlp_http.py        [MOD] build resolver from repository; pass to normalizer
│
├── storage/
│   ├── base.py                        [MOD] add put_pending_trace / get_pending_trace to Protocol
│   └── sqlite.py                      [MOD] pending_trace_correlation table + methods
│
├── demo/
│   ├── loan.py                        [MOD] minimal: wrapped by python_fn adapter; outcomes unchanged
│   └── langchain_agent.py             [ADD] runnable LangChain HTTP agent sample service: POST /invoke,
│        openinference instrumentation, OTLP/HTTP JSON export, W3C traceparent propagation,
│        env-var provider key; entrypoint `python -m agentgate.demo.langchain_agent` — see §B
│
├── case/                              [KEEP]
├── evaluator/                         [KEEP]
├── result/                            [KEEP]
└── run/external/                      [DEFER] framework adapters (langchain/autogen/openai_agents)

tests/
├── test_target_models.py             [ADD] identity, immutability, hashes, secret exclusion
├── test_http_target.py               [ADD] fake external HTTP platform + adapter + error taxonomy
├── test_trace_correlation.py         [ADD] pending mapping + resolver + degraded fallback + N/A semantics
├── test_run_engine_target.py         [ADD] RunEngine uses snapshot+adapter; inline vs await paths
├── test_demo_engine.py               [MOD] assert Run uses TargetSnapshot without hard-coding (non-regression)
└── fake_http_agent.py                [ADD] test fixture: HTTP /invoke + OpenInference-style OTLP export
```

```text
web/                                     [MOD] data-driven target selection (§C); no routing logic in browser
├── src/api/client.ts                  [MOD] widen Version type (adapter_type?/endpoint?); api.versions() and
│                                           api.launch(target_id, ...) signatures unchanged; optional api.launchHttp()
├── src/App.vue                        [MOD] agent <el-select> lists registry targets; label shows adapter_type
│                                           (Demo vs HTTP); selectedVersion default stays a loan id (non-regression)
└── src/pages/DatasetWorkspace.vue     [MOD] dataset-run-bar agent select lists registry targets; selectedAgent
                                           default stays a loan id; launchEvaluation() unchanged
```

[KEEP] modules consume the canonical Trace only (invariant #5) and need no change.

## 10. Acceptance Criteria

Short-term subset of external-target-plan §Acceptance Tests (numbers in brackets are the
originating item there). Items requiring catalog/trace-only/process/instrumented-demo are
deferred.

### Domain contracts

1. `TargetType` accepts `agent`/`skill`, rejects unknown values. [#1]
2. `TargetRef` requires all four identity fields, non-empty. [#2]
3. `TargetSnapshot` is deeply immutable and content-hashed; secrets cannot enter any
   field (a plaintext credential field is rejected). [#3, #5]
4. Changing target version / adapter version / `invocation_config` changes `RunSnapshot`
   hash. [#4]

### Adapter and HTTP path

5. `PythonFunctionTarget` uses the normalized request/result contract; loan risky/fixed
   versions retain current Gate outcomes (fail / pass). [#9, #11]
6. `HttpTargetAdapter` invokes the exact external version (no silent "latest" fallback).
   [#12, drift rule 8]
7. `HttpTargetAdapter` sends `traceparent`, `Idempotency-Key`, `X-AgentGate-Run-Id`,
   `X-AgentGate-Case-Id`, `X-AgentGate-Turn-Id` (when present). [#13]
8. The adapter rejects malformed content-type or response shape (`protocol_error`). [#14]
9. 401→`unauthorized`, 404→`target_not_found`, 429→`rate_limited`, timeout→`timeout`,
   5xx→`unavailable`; public errors and logs redact `Authorization`/tokens. [#15, #16]
10. An inline Trace (from the python adapter) must match the request run/case identity; a
    mismatch is rejected. [#19]

### Trace correlation

11. A separately emitted OTLP Trace is correlated by `trace_id` via the pending mapping
    when the Agent does **not** stamp `agentgate.*` attributes. [#20]
12. When the Agent **does** stamp `agentgate.*` attributes, correlation still works without
    the pending mapping (priority order respected).
13. OpenInference `openinference.span.kind` and OTel GenAI `gen_ai.*` spans map to canonical
    `SpanKind` per §4 Q4 (LLM/AGENT/CHAIN→AGENT, TOOL→TOOL, RETRIEVER→TOOL, others→EVENT).
14. `trace_timeout` (OTLP does not arrive within `trace_wait_seconds`) yields a degraded
    Trace: span-dependent evaluators report N/A; output/state evaluators run; a
    `trace_timeout` warning is recorded on the Run; it is **not** an Agent FAIL. [#21
    analogue; external-target-plan §Trace Correlation]
15. Target invocation errors stop evaluation and never become Agent FAIL (invariant #9).
    [#21]

### End-to-end

16. End-to-end with a fake HTTP Agent fixture:
    - author/publish a real Dataset + Case;
    - launch an HTTP target (endpoint + ref + credential_ref env var);
    - RunEngine invokes the fake Agent with `traceparent`;
    - the fake Agent returns output/state/trace_id and exports OpenInference-style OTLP to
      `/v1/traces`;
    - the canonical Trace appears with mapped spans; evaluation produces a Result; the
      report and Run snapshot resolve the exact external identity;
    - the trace drill-down (existing Web/API path) shows real spans.
17. Loan demo non-regression: `agentgate evaluate --version loan-agent-v1-risky` → fail;
    `loan-agent-v2-fixed` → pass; existing Web/E2E flows unchanged.

### Target routing & Web selection

18. The service registry lists both the loan demo target(s) and the LangChain HTTP agent
    sample (§A, §B); `GET /api/versions` returns them with distinguishing labels and
    `adapter_type` (and `endpoint`/`credential_ref` where applicable).
19. Selecting a loan demo target routes to `PythonFunctionTarget(LoanAgent)`; selecting
    the LangChain HTTP agent routes to `HttpTargetAdapter`; both go through the same
    `launch_target` → RunEngine path with no special-case branch (invariant #12).
20. The Web launch UI (`App.vue`, `DatasetWorkspace.vue`) renders the registry list in the
    agent selector and forwards only the `target_id` to the API — no routing logic in the
    browser (invariant #12). Loan demo launch via the UI is non-regression (defaults and
    existing `data-testid` selectors unchanged).
21. Launching the LangChain HTTP agent from the Web end-to-end: the sample service returns
    output/state/trace_id and exports OpenInference-style OTLP; the canonical Trace +
    Result + report appear with real spans; the trace drill-down shows canonical kinds
    mapped from OpenInference (§8).

### Quality gate (AGENTS.md §4)

- `ruff check .` clean.
- `python -m pytest -q` green (new tests + existing non-regression).
- `cd web && npm run typecheck` + `npm run build` + `npm run test:e2e` green. The Web
  launch selector change (§C) must pass typecheck/build/E2E; existing loan demo E2E stays
  green (non-regression).

## 10.5. Single-Case Rerun Compatibility

### Background

This plan was authored against the `goal/p1-demo` baseline and does not cover the
single-Case rerun capability delivered later by PR #2 (merged into `integration/p1`).
A design check found that two contracts in this plan would **break** rerun if applied
verbatim:

- §5 moves `version` out of `TargetSnapshot` (into `ref.external_version_id`), but
  `control_plane/service.py` `rerun_case` rewrites `source.snapshot.target.version` to
  pin a rerun to a different target version.
- §6 gives a trimmed `RunEngine.run` signature that drops the rerun-specific parameters
  (`metric_plan` / `gate_spec` / `selected_case_ids` / `parent_run_id` / `root_run_id` /
  `rerun_case_id`) the current signature (see `src/agentgate/run/core.py` lines 44-52) and
  `rerun_case` rely on.

This section merges the rerun contracts into the new target/adapter contracts. The
adaptation is docs-first (this plan is the design source) and is implemented together
with §5-§7; it is not a separate increment.

### Adaptation points

1. **`RunEngine.run` new signature must retain the rerun parameters.** The trimmed
   signature in §6 is insufficient. The merged signature replaces `target` +
   `target_version` + `provider` with `dataset_version` + `target_snapshot` + `adapter`
   (per §6) **and** retains every rerun parameter from the current signature:

   ```text
   run(dataset_version, target_snapshot, adapter, evaluators,
       *, metric_plan=None, gate_spec=None, selected_case_ids=None,
       parent_run_id=None, root_run_id=None, rerun_case_id=None,
       trace_wait_seconds=30.0, trace_poll_interval_seconds=0.5)
   ```

   `target_snapshot` / `metric_plan` / `gate_spec` / `selected_case_ids` /
   `parent_run_id` / `root_run_id` / `rerun_case_id` are all kept; `target` +
   `target_version` + `provider` are removed (subsumed by `target_snapshot` + `adapter`).
   The hard-coded `name="loan-agent"` fallback (current `run/core.py` lines 68-69) is
   removed as §6 requires; rerun always supplies an explicit `target_snapshot`.

2. **`rerun_case` version rewrite must target `ref.external_version_id`.** The current
   `rerun_case` (see `src/agentgate/control_plane/service.py` line 78) does
   `source.snapshot.target.model_copy(update={"version": version})`. Under the new
   `TargetSnapshot` (§5) there is no `version` field; the version lives in
   `ref.external_version_id`. The rewrite becomes:

   ```text
   target_snapshot = source.snapshot.target.model_copy(
       update={"ref": source.snapshot.target.ref.model_copy(
           update={"external_version_id": version}
       )}
   )
   ```

   The `if version not in LoanAgent.versions` check (current lines 76-77) is replaced by a
   lookup through the **local target registry** (§A): validate the `target_id` /
   `external_version_id` pair against registered targets and reject with
   `target_not_found` (or `version_not_found` when the catalog lands) **before
   execution**. The hard-coded `LoanAgent.versions` membership test is removed.

3. **`rerun_comparison` version reads must use `ref.external_version_id`.** The current
   `rerun_comparison` (see `service.py` lines 142-143) reads
   `parent.snapshot.target.version` and `rerun.snapshot.target.version`. Under the new
   structure these become `parent.snapshot.target.ref.external_version_id` and
   `rerun.snapshot.target.ref.external_version_id`. No other change to the comparison
   contract.

4. **`rerun_case` adapter source must follow `adapter_type`.** The current `rerun_case`
   hard-codes `LoanAgent(self.repository)` (line 81). Under the new architecture the rerun
   rebuilds the adapter from the **source snapshot's `adapter_type`**: if
   `adapter_type == "python_fn"` rebuild `PythonFunctionTarget(LoanAgent(self.repository))`;
   if `"http"` rebuild `HttpTargetAdapter` from the registry entry (`endpoint` +
   `credential_ref`, resolved by `EnvCredentialResolver`). The rerun may delegate to the
   registry's `build()` factory (§A) or dispatch by `adapter_type` within the service.
   **Routing stays in the service** (invariant #12); no adapter selection logic in
   CLI/API/Web.

5. **`latest_target_version()` must go through the registry.** The current static method
   (see `service.py` lines 93-95) returns `LoanAgent.versions[-1]`. Under the new
   architecture it queries the local target registry (§A) — return the latest
   `external_version_id` of a designated default target, or accept a `target_id` argument
   and look up that target's latest version. The concrete return shape is left to the
   implementer, but the contract direction is: **no hard-coded `LoanAgent.versions`
   reference**; the registry is the single source of target/version truth.

6. **Rerun reuses the §4 inline/await trace paths — no new mechanism.** The current rerun
   targets only the loan demo, which goes through `PythonFunctionTarget` and therefore the
   **inline_trace path** (§6 `python_fn` adapter: `inline_trace=<returned Trace>`,
   RunEngine consumes it directly, no OTLP await). A future `rerun_http` (not in this
   increment) would follow the §4 await path (pending mapping + `trace_wait_seconds`).
   The rerun path **does not** introduce a third correlation mechanism; it branches on
   the same `inline_trace is not None` check (§4 step 7) as the primary run.

### Acceptance

22. Single-Case rerun (loan demo) works under the new `TargetSnapshot` + adapter
    architecture: `rerun_case` rewrites `ref.external_version_id`;
    `rerun_comparison` reads `ref.external_version_id`; the rerun's Gate outcome matches
    the pre-PR-#2 behavior (non-regression). The rerun `Run` carries `parent_run_id` /
    `root_run_id` / `rerun_case_id` exactly as today.

### Invariants

These adaptations introduce **no new** Architecture Rule violation: rerun remains Run
orchestration (#2); a rerun target/trace error is an execution error, not an Agent FAIL
(#9); `credential_ref` stays an opaque id, never a secret (#15); adapter routing lives
in the service, not in UI/API (#12).

## 11. Path Migration Note (refactor-1)

> Confirmed: short-term uses `run/targets/` paths on `integration/p1`; migration to
> `integrations/targets/` deferred until `refactor-1` is created.

This plan uses the **`goal/p1-demo`** paths: `run/targets/` for adapters and `run/core.py`
for the RunEngine + `Target` boundary. It does **not** adopt the
`architecture-review-ledger.md` paths (`integrations/targets/` for adapters +
`run/target_protocol.py` for the execution protocol).

Rationale:

- The `refactor-1` implementation branch is not yet created; the ledger is an architecture
  review record, not an implementation.
- The short-term goal is to run a real HTTP Agent end-to-end as fast as possible on
  `goal/p1-demo`, where `run/targets/` already exists (as empty scaffolds) and `run/core.py`
  already hosts the working RunEngine.
- Migrating paths mid-increment would force a broader refactor of `run/` (engine rename,
  `process_manager.py`, `manifest.py`, `artifacts.py`) that is out of scope.

Migration at `refactor-1`:

- `run/targets/http.py`, `python_fn.py`, `base.py` → `integrations/targets/` (e.g.
  `http_agent.py`, plus python/process equivalents).
- The `TargetExecutionAdapter` Protocol → `run/target_protocol.py` (the ledger's
  `start`/`get_status`/`wait`/`cancel` minimal protocol is a superset for async
  scheduling; the synchronous `execute(request) -> result` contract here is the POC shape
  and will be reconciled with the async protocol when `process_manager.py` lands).
- `domain/target.py` stays in `domain/` (the ledger keeps domain contracts in `domain/`).
- The pending-mapping correlation surface is reconciled with
  `docs/trace/ingestion-plan.md` (merge/dedup/completeness) at refactor-1.

This path decision is recorded here so the `refactor-1` owner can migrate without
re-discovering the rationale.

## 12. Deferred Work

Carried to later increments (mirrors external-target-plan §Deferred Work where relevant):

- Full catalog adapter that queries an external platform API
  (`list_targets`/`list_versions`/`get_descriptor`) + `TargetDescriptor` /
  `ToolDescriptor` / `SkillDescriptor` full metadata. Local target **registration / listing /
  routing** is in scope (§A); external-platform discovery is not.
- A dedicated `run/targets/demo.py` catalog/execution adapter (short-term wraps LoanAgent
  via `python_fn`).
- Process adapter, trace-only adapter.
- LangChain/autogen/openai_agents framework SDK adapters (`run/external/*.py`).
- Production credential vault (`docs/security/credentials-plan.md`); POC uses
  `EnvCredentialResolver`.
- Full `ExecutionPolicy` model (timeout/retry/cancellation/idempotency); short-term uses
  RunEngine parameters with POC defaults. Retry policy belongs to Run/scheduler, not hidden
  adapter loops (external-target-plan rule 7).
- Unified `POST /api/runs` API (external-target-plan §API Boundary); short-term keeps demo
  `POST /api/evaluations` + new `POST /api/evaluations/http`.
- Target CRUD/management Web screens. Target **selection** in the launch UI is in scope
  (§C); creating/editing/publishing targets from the Web is not.
- OTLP/gRPC. OTLP/HTTP merge, deduplication, completeness, and protobuf support are now
  implemented under `docs/trace/ingestion-plan.md`.
- Pending-mapping cleanup (TTL / run-completion sweep) — ingestion-plan scope; the POC
  table is non-destructive and will grow slowly.
- The full instrumented Demo Agent HTTP service per `docs/run/demo-agent-plan.md` (a
  broader, separate increment). The short-term `demo/langchain_agent.py` sample (§B) + the
  fake HTTP Agent fixture together cover real HTTP + OTel export for tests and manual/Web
  runs; the demo-agent-plan service remains its own increment.
- `run/snapshot.py` / `run/lifecycle.py` split (external-target-plan MOD); short-term keeps
  the logic in `run/core.py`.
- `version_not_found` catalog-relevant error branch (exercised when the catalog lands).

---

## Supplement A — Target Registration, Selection, and Routing

### Problem

`control_plane/service.py` hard-wires a single target: `launch` instantiates
`LoanAgent(self.repository)` (line ~40) and `versions()` returns only `LoanAgent.versions`
(lines ~65-72). The Web selector therefore lists only loan demo versions and every
selection runs LoanAgent. The short-term goal needs multiple selectable targets (loan demo
+ a real LangChain HTTP agent sample) routed through one launch path.

### Design — local target registry

This is **not** the full catalog adapter (no external-platform API discovery); it is a
local configuration of known targets, owned by `EvaluationService`. The registry maps
`target_id → TargetRegistration`:

```text
TargetRegistration:
  target_id            # stable id used by Web/CLI/API
                       #   e.g. "loan-agent-v2-fixed", "langchain-http-agent"
  label                # human label for the Web selector
  adapter_type         # "python_fn" | "http"
  target_ref           # TargetRef (platform_id / target_type / external_target_id / external_version_id)
  invocation_config    # endpoint + non-secret headers (http only); empty for python_fn
  credential_ref       # opaque env-var name (http only); None for demo
  build()              # factory -> (TargetSnapshot, TargetExecutionAdapter) for this target
```

Registered targets (POC):

- loan demo risky + fixed → `PythonFunctionTarget(LoanAgent(...))` (inline_trace path);
  `credential_ref=None`; `adapter_type="python_fn"`.
- langchain HTTP agent sample (§B) → `HttpTargetAdapter(endpoint, EnvCredentialResolver())`;
  `credential_ref` = env-var name; `endpoint` points at the sample service;
  `adapter_type="http"`.

### Surface changes

- `versions()` → `list_targets()`: returns the registry as
  `[{target_id, label, adapter_type, endpoint?, credential_ref?}]`. The HTTP route stays
  `GET /api/versions` (Web `api.versions()` URL unchanged) so existing `Version[]`
  consumers keep working; the `Version` type widens with optional `adapter_type`/`endpoint`
  (§C). Loan demo ids remain unchanged for non-regression.
- `launch(target_id, dataset_id, dataset_version, evaluator_ids)`: looks up the registry by
  `target_id`; on miss → `target_not_found` (rejected **before execution**, per the
  external-target-plan error rule). On hit → `build()` produces
  `(TargetSnapshot, TargetExecutionAdapter)`; calls `launch_target(...)`. Loan version
  strings are valid `target_id`s (non-regression).
- `launch_http(...)`: remains as the explicit programmatic HTTP entry that bypasses the
  registry for ad-hoc endpoints; used by `agentgate evaluate-http` CLI and
  `POST /api/evaluations/http`.

### Invariants

- #6: the loan demo and the langchain sample agent are **AgentGate demo assets** (like
  `LoanAgent` today), not user external assets. A real production Agent is external and is
  reached via the HTTP adapter; AgentGate never manages any Agent's lifecycle.
- #12: routing lives in the service; Web/CLI/API only pass `target_id`. No routing logic in
  `App.vue` / `DatasetWorkspace.vue` / FastAPI routes.
- #15: `credential_ref` is an opaque env-var name; the registry stores no secret.
  `EnvCredentialResolver` reads the env var at execute time inside the adapter.

### Non-regression

Loan demo ids (`loan-agent-v1-risky`, `loan-agent-v2-fixed`) remain in the registry and map
to the existing demo path; existing CLI `agentgate evaluate --version ...`,
`POST /api/evaluations`, and Web launch produce the same Gate outcomes.

## Supplement B — LangChain HTTP Agent Sample Service

### Purpose

A runnable sample Agent HTTP service under `demo/` that demonstrates the "real HTTP agent
+ OTel export" integration mode end-to-end, standing in for a production external Agent.
Like `LoanAgent`, it is AgentGate demo code (invariant #6: demo asset, not external), but
it is a real HTTP service emitting real OTel telemetry rather than an inline synthetic
Trace.

### Location & entrypoint

- File: `src/agentgate/demo/langchain_agent.py` (name finalized at implementation;
  alternative: `demo/http_agent_service.py`).
- Runnable: `python -m agentgate.demo.langchain_agent` — a FastAPI app on a configurable
  port (`AGENTGATE_LANGCHAIN_AGENT_PORT`, default e.g. 8081).
- OTLP export target: standard OTel SDK env (`OTEL_EXPORTER_OTLP_ENDPOINT`,
  `OTEL_EXPORTER_OTLP_PROTOCOL=http/json`, optional `OTEL_EXPORTER_OTLP_HEADERS`) wired to
  AgentGate's `POST /v1/traces`. The implementer configures `OTLPSpanExporter` from these.

### HTTP contract

- `POST /invoke` accepts the AgentGate `TargetExecutionRequest` body
  (`{invocation_id, idempotency_key, target{type,id,version_id}, run_id, case_id,
  turn_id, input, state}`) and reads the `traceparent`, `Idempotency-Key`,
  `X-AgentGate-Run-Id`, `X-AgentGate-Case-Id`, `X-AgentGate-Turn-Id` headers set by
  `HttpTargetAdapter` (§6).
- Returns `{invocation_id, external_execution_id, output, final_state, trace_id}` — the
  shape `HttpTargetAdapter` validates.
- `trace_id` is echoed from the `traceparent`'s trace_id so AgentGate can correlate even
  if OTLP is delayed (defense in depth alongside the pending mapping in §4).

### Agent implementation (kept simple — sample, not production)

- A minimal LangChain chain or agent (e.g. one LLM call + one tool) over the Case `input`.
  The task is chosen to be trivially evaluable (e.g. a decision with a state update) so
  rule evaluators have something to check. Complexity is intentionally low to avoid
  heavy/fragile dependencies — the point is the HTTP + OTel **integration pattern**, not
  agent sophistication.
- Instrumented with `openinference-instrumentation-langchain`
  (`LangChainInstrumentor().instrument()`) so spans carry `openinference.span.kind` +
  `llm.*`/`tool.*` attributes — the scheme the normalizer rules in §8 target.
- Uses the OTel SDK to propagate the incoming `traceparent` (the Agent's spans inherit the
  AgentGate-generated trace_id) and to export OTLP/HTTP JSON to AgentGate.

> Dependencies (`openinference-instrumentation-langchain`, `opentelemetry-sdk`,
> `langchain`) are declared under `[project.optional-dependencies] demo` in `pyproject.toml`;
> the sample runs a deterministic stub when no LLM provider key is set so CI needs no
> provider key (§B Security). Tests use the in-process `fake_http_agent.py` fixture, not
> the live service.

### Security

- #7: no hardcoded keys. Any LLM provider key (e.g. OpenAI) comes from an environment
  variable (`OPENAI_API_KEY`); the sample fails loudly if absent rather than embedding a
  secret.
- #15: the service never logs `Authorization`/provider keys; OTLP export headers are not
  treated as evaluator evidence.
- The sample may optionally run without a real LLM (a deterministic stub) so tests/CI do
  not require a provider key; the OTel instrumentation still emits spans.

### Relationship to plans

- This is **not** the full `docs/run/demo-agent-plan.md` instrumented Demo Agent service (a
  broader, separate increment; see §12). It is a minimal sample sufficient to exercise the
  HTTP adapter + OTel correlation + Web selection end-to-end.
- It is **not** a framework adapter under `run/external/langchain.py` (deferred) — AgentGate
  does not import the LangChain SDK; the sample just happens to be built with LangChain and
  exposes a plain HTTP API.

### Tests

- `tests/fake_http_agent.py` (already in §9) is the in-process test double for automated
  tests. The `demo/langchain_agent.py` sample is for **manual and Web end-to-end** runs
  (started as a separate process). Acceptance #21 (§10) launches it from the Web.

## Supplement C — Web Launch Multi-Target Selection

### Problem

`App.vue` (`selectedVersion = ref('loan-agent-v2-fixed')`, agent `<el-select>` iterating
`versions`, `api.launch(selectedVersion.value, ...)`) and `DatasetWorkspace.vue`
(`selectedAgent = ref('loan-agent-v2-fixed')`, `launchEvaluation` →
`api.launch(selectedAgent.value, ...)`) list only loan demo versions and route every
selection to LoanAgent. They must list all registered targets and route by `target_id`.

### Design (data-driven, minimal)

- `api.versions()` (`GET /api/versions`) now returns the registry listing (§A). The
  `Version` type widens:
  ```text
  interface Version {
    id: string          // target_id
    label: string
    adapter_type?: 'python_fn' | 'http'
    endpoint?: string
  }
  ```
  The URL and `api.launch(version, ...)` signature stay unchanged — the first arg is now a
  `target_id`. No new client method is required for the registry-based flow.
- `App.vue`: the agent `<el-select>` already iterates `versions`; only the label template
  changes to surface `adapter_type` so loan demo and the langchain HTTP agent are
  distinguishable (e.g. `"${item.label} · ${item.adapter_type === 'http' ? 'HTTP' : 'Demo'}"`).
  `selectedVersion` default stays a loan id (non-regression). `launch()` is unchanged
  (passes `selectedVersion.value` as `target_id`).
- `DatasetWorkspace.vue`: same data-driven change in the dataset-run-bar agent
  `<el-select>`; `selectedAgent` default stays a loan id; `launchEvaluation()` is unchanged.
- Optional (for ad-hoc HTTP): an `api.launchHttp(...)` client method + a small "custom HTTP
  endpoint" affordance may be added, but is **not required** for the registry flow (the
  langchain sample is a registered target). Defer the custom-endpoint UI unless needed.

### Invariants

- #12: the browser performs **no routing** — it only renders the registry list and forwards
  the selected `target_id`. The service resolves `target_id → adapter`. No adapter/endpoint/
  credential logic is duplicated in Vue.
- #15: the browser never sees credentials. `credential_ref` (env-var name) may be shown for
  transparency; the secret value is never returned by `GET /api/versions`.

### Non-regression

- Loan demo ids remain in the listing; default selection and existing E2E selectors
  (`data-testid="agent-select"`, `dataset-agent-select`) keep working.
- The trace drill-down (`trace.spans[].kind`) now shows canonical kinds mapped from
  OpenInference (§8) when the langchain agent is selected.

### Quality gate

- `npm run typecheck` + `npm run build` + `npm run test:e2e` must pass with the widened
  `Version` type and the selector label change. Existing loan demo E2E stays green.
