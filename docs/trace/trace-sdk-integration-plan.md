# trace-sdk 集成计划：Trace 生成/上报/接收切换（OTel → trace-sdk）

> [!IMPORTANT]
> 本文为**切换设计文档（v0.1 评审定稿版）**。Agent 侧 trace 的产生/上报由
> OpenTelemetry（OTLP/HTTP push）切换为自研 trace-sdk（事件模型，file/Redis/Kafka/直写）。
> 评测中间层（canonical Trace / merge / completeness / 存储 / 评测器）**不受影响**。
> OTLP 接收通道在灰度窗口内保留。原设计见 [ingestion-plan](ingestion-plan.md)。
> 决策记录见 [architecture-review-ledger](../architecture-review-ledger.md)。

## 状态

- 版本：v0.1（2026-09-04 评审通过稿）
- 代码基线：`integration/p1-new`（`50168e6`）
- trace-sdk 基线：`/Users/baibo/01-XunZhan/trace-sdk`（tracev2-master）
- 实施状态：未开始（G0 前置项未关闭）

## 目标

1. LangChain 架构的被测 Agent **即插即用**：挂载 trace-sdk `CallbackHandler` 即完成全部埋点（替代当前每家 Agent 手工拼 OTLP JSON）。
2. 获得 LLM 语义富信息（token 明细、TTFT、真实 LLM 请求报文），为 LLM Judge 评估器（PRD P2）铺路。
3. **保住评测链路全部既有保障**：幂等、冲突、确定性排序、完整性门槛、修订与 Result 证据锚定。
4. 最小改动、可灰度、可回退。

## 非目标

- 不替换 canonical Trace 中间层（merge / completeness / 存储 / 修订）；
- 不迁移 demo python_fn 目标（inline trace 路径不动）；
- 不替代 trace-sdk 的 Trace Monitor UI；
- 不在本次解决 trace-sdk 自身的工程缺口（列为 G0 外部前置项，见 §9）。

## 背景对比

### 范式差异

| 维度 | OTel 方式（原设计） | trace-sdk 方式（新） |
|---|---|---|
| 血统 | OpenTelemetry 标准（span/tracer/exporter 管线） | Langfuse 形态（自研，差分测试对标 Langfuse） |
| 数据模型 | 统一 Span（traceId/spanId/parent/kind/attributes） | 5 类事件：TraceEvent / SpanEvent / ObservationEvent / SessionEvent / LLMRequestEvent |
| 目标场景 | 通用分布式追踪（语言无关） | LangChain Agent 专用（Python + 回调） |
| 运行依赖 | 零额外依赖（HTTP POST + SQLite） | Redis / Kafka / PostgreSQL 任一（file 模式仅同机） |
| 上报 | 同步 `POST /v1/traces`，响应返回前发完 | 异步缓冲（batch 100 / 2s flush），无 HTTP 摄取端点 |
| 幂等 | 接收端 span 身份 + 内容哈希 | 事件 `event_id`（UUID）作幂等键 |
| 采样/脱敏 | 无 | 确定性头采样 + 错误强制保留 + 脱敏规则 |

### 生成侧差异

| | OTel | trace-sdk |
|---|---|---|
| 接入 | 手工构造 span + 属性约定 | `TraceClient(config)` + `CallbackHandler()` 挂 `config={"callbacks":[...]}` |
| 父子关系 | 手工指定 parentSpanId | `_runs` 映射（Langfuse 同款语义） |
| 工具名 | `tool.name` 属性；评测匹配要求 span.name == 工具名（隐式契约，易踩坑） | LangChain 工具回调 run name 天然即工具名 |
| 跨进程传播 | traceparent 头（引擎 → Agent） | 手工 body 字段（`trace_context`） |

## 总体架构：只换两头，保住中间

```text
【生成侧 · 换】
被测 Agent（LangChain）
  └─ trace-sdk CallbackHandler（自动采集，span_type = chain/llm/tool/retriever/agent/span）
  └─ agentgate_bridge.py（新增，约 100 行，运行在 Agent 进程内）
       ├─ 从 invoke body 取 run_id/case_id/turn_id/invocation_id → 写入事件 metadata
       ├─ trace_context 注入 AgentGate 的 trace_id（pending 关联表照常工作）
       └─ 响应前 client.flush()（保住评测及时性）

【传输 · 换】
file（同机默认：JSONL，每 trace 一文件）或 Redis Stream（跨机）

【接收侧 · 换】
trace/receivers/trace_sdk.py（新增）
  ├─ file 模式：约定目录增量拉取（容忍半行，下轮重读）
  ├─ Redis 模式：XREAD（独立 consumer group，不干扰 trace_consumer）
  └─ 事件 → NormalizedSpan / NormalizedSignal（normalizer 新分支）

【中间与下游 · 全部不动】
merge（幂等/冲突/优先级） → completeness → trace_* 表
→ RunEngine 轮询至 COMPLETE → 评测器 → Result（锚定 Trace 修订/哈希）

【并行保留】receivers/otlp_http.py（灰度窗口期，存量 OTel 目标继续可用）
```

设计依据：中间层消费的是 `NormalizedSpan` 而非 OTLP 原文——这是 ingestion-plan
"评测器永不解析 OTLP"（反漂移规则 #8）的推论。换线格式不需要重写评测证据链。

## 关联桥接设计（四个鸿沟）

### A. run/case 关联缺失

trace-sdk 事件模型只有 project/session/trace，没有 run/case 概念。

桥接：`agentgate_bridge.py` 从 invoke 请求体（AgentGate HTTP 适配器本来就发送
run_id/case_id/turn_id/invocation_id）取出关联字段，写入 SpanEvent/TraceEvent 的
`metadata`。归一化分支读取 metadata 补齐 correlation，等价于原 OTLP 路径的
`agentgate.run.id` / `agentgate.case.id` 属性。

### B. 跨进程传播通道变化

OTel 靠 traceparent 头；trace-sdk 的 W3C helper 存在但未接线，实际靠 body 字段。

桥接：桥接层用 `CallbackHandler(trace_context={"trace_id": <AgentGate trace_id>})`
强制子 Agent 的 trace_id 等于引擎在 `pending_trace_correlation` 登记的值。
**pending 表按 trace_id 匹配的核心机制原样保留**，仅注入通道从头变为桥接构造。
traceparent 头照发（HTTP 适配器零改动），Agent 侧忽略亦可。

### C. 终态信号与 final_state 缺失

trace-sdk 无 `agentgate.trace.complete` / `final_state.json` 等语义信号。

桥接（双路供给）：

1. **trace 级完成**：归一化分支把 TraceEvent 落地（`end_trace` 时产生，语义 =
   本次 Agent 运行结束）映射为 `trace_complete` 信号；
2. **final_output**：TraceEvent.output 映射为 `final_output` 信号；
3. **final_state**：不依赖事件——走既有优先级链顶端"适配器执行结果"：HTTP invoke
   响应体必含 `final_state`（评测对象接入契约），引擎已有机制直接采用，**零改动**；
4. **turn 级完成**：trace-sdk 无 turn 概念。单轮用例以 trace_complete 兼代；多轮
   用例为已知限制（§8），POC 阶段桥接层为每轮注入独立 trace，按轮聚合。

### D. 接收通道缺失

trace-sdk 无 HTTP 摄取端点。新增 `trace/receivers/trace_sdk.py`：

- **file 模式**（同机默认，零基建）：监控约定目录
  `<root>/<project_id>/<session>/<trace_id>.jsonl`，按 mtime 增量拉取；
- **Redis 模式**（跨机）：XREAD 消费 `trace_topic`（独立 consumer group）；
- Kafka 模式按需后补（接口对齐 Redis 分支）。

两种模式拉回事件后统一进 normalizer 新分支 → merge → completeness，与 OTLP
路径在 NormalizedSpan 处汇合。

## 事件归一化映射表（兼容性契约，定稿冻结）

| trace-sdk 事件/字段 | AgentGate NormalizedSpan / 信号 | 说明 |
|---|---|---|
| SpanEvent | NormalizedSpan | 一对一 |
| SpanEvent.trace_id / span_id / parent_span_id | source_trace_id / source_span_id / parent_span_id | 身份三件套直接平移 |
| SpanEvent.span_type = tool | SpanKind.TOOL | 关键映射：必需/禁用工具评估器依赖 |
| SpanEvent.span_type = agent / chain | SpanKind.AGENT | |
| SpanEvent.span_type = llm | SpanKind.AGENT（属性保留 span_type） | 观测价值为主 |
| SpanEvent.span_type = retriever | SpanKind.TOOL | 对齐现有 openinference 映射惯例 |
| SpanEvent.name | NormalizedSpan.name | 工具场景下天然即工具名 |
| SpanEvent.input / output / metadata | attributes（点路径 `span.input` / `span.output` / `metadata.*`） | 含桥接写入的 run/case 关联 |
| SpanEvent.started_at / duration_ms | start_time_unix_nano / end_time_unix_nano | ISO-8601 → 纳秒换算 |
| SpanEvent.status = error | status="error" + attributes 保留 error_info | |
| TraceEvent | 终态信号组 | `end_trace` 时产生 |
| TraceEvent.output | final_output 信号 | |
| TraceEvent.status | trace_complete 信号（success/error 均视为完成） | |
| final_state | 无映射（走 invoke 响应，适配器结果优先级最高） | 见 §C-3 |
| ObservationEvent / LLMRequestEvent | attributes 附加（`llm.*`） | 评测暂不消费，留 LLM Judge 用 |
| SessionEvent | 不映射 | 会话语义与 run/case 不同构 |

## 代码改动清单

| # | 改动 | 类型 | 规模估计 |
|---|---|---|---|
| 1 | `agentgate_bridge.py`（桥接 handler，Agent 进程内） | 新增 | ~100 行 |
| 2 | `trace/receivers/trace_sdk.py`（file + Redis 双模式） | 新增 | ~200 行 |
| 3 | `trace/normalizer.py` 事件归一化分支 + 映射表 | 修改 | ~120 行 |
| 4 | `server/application.py` 接收器启动接线（env 开关 `AGENTGATE_TRACE_SDK_*`） | 修改 | ~20 行 |
| 5 | 假 Agent（`tests/fake_http_agent.py` / `fake_agent_server.py`）增加 trace-sdk 嵌入模式 | 修改 | ~80 行 |
| 6 | 测试：L1 归一化映射 / L2 file+Redis 拉取 / L4 E2E 闭环 | 新增 | ~400 行 |

不改动：`trace/merge.py`、`trace/completeness.py`、`storage/` trace 表、
`run/core.py` 轮询、`run/targets/http.py`、评测器、`result/`、demo python_fn、
OTLP 接收器（保留）。

## 灰度与回退

| 阶段 | 内容 | 退出条件 |
|---|---|---|
| G0 前置 | trace-sdk 工程缺口修复（§9）；桥接 handler 单测 | 缺口关闭 |
| G1 并行 | trace_sdk 接收器上线（env 开关），OTLP 照常；假 Agent 双模式 E2E | 全量测试绿（332 旧测试零修改） |
| G2 迁移 | 真实目标（如 Ticket-Approv-Agent）切 trace-sdk；demo OTel agent 保留 | 至少 1 个真实目标全链路绿 |
| G3 收口 | OTLP 接收器标记 deprecated（保留不删，随时回退） | 团队确认 |

回退：任一阶段关闭 env 开关即回 OTLP 路径；中间层未动，评测数据零迁移。

## 已知限制（评审已接受）

1. 多轮用例完整性判定退化为轮级 trace 聚合（同构性弱于 OTLP 的 turn 信号）；
2. 技能路由评估器（ROUTING span / selected_skill）在 trace-sdk 路径恒不适用——
   用例不设 expected_skill 即不触发；如需要，桥接层可在 span metadata 补
   `selected_skill`（可选增强，另行评审）；
3. Python-only：非 LangChain / 非 Python 的被测目标仍走 OTLP 通道（灰度窗口
   永久保留的原因之一）。

## 外部前置项（G0，阻塞级）

| # | 问题 | 处置 |
|---|---|---|
| R1 | trace-sdk 副本缺 `trace_consumer/fields.py`（writer.py 引用），consumer 与 direct_db 后端跑不起来 | trace-sdk 仓库补齐；file 模式不受影响 |
| R2 | SpanEvent 的 `metadata/tags/level/model_parameters/TTFT` 采集了但 PG schema 与 writer 未落库 | 桥接依赖 metadata 传关联字段——file 模式 JSONL 原样保留不受影响；走 Redis/PG 需 trace-sdk 先补 schema |

其他风险与缓解：异步 flush 时延（桥接响应前强制 flush + E2E 时延断言）、
file 半行读取（接收器容错，跳过半行下轮重读）、trace-sdk 无鉴权（同机 file 模式
规避；跨机部署网络隔离，列入部署清单）。

## 验收测试（新增）

1. SpanEvent（span_type=tool，name=工具名）归一化后通过必需/禁用工具评估器；
2. TraceEvent 落地触发 trace_complete，Trace 状态收敛 COMPLETE；
3. final_state 来自 invoke 响应（适配器结果优先级），与事件无关；
4. 桥接注入的 trace_id 与 pending_trace_correlation 匹配，无需 run/case 属性回退；
5. 同一事件文件重复拉取幂等（duplicate 计数，不产生冲突）；
6. file 半行容错：部分写入的 JSONL 行跳过并在下轮重读；
7. 事件 metadata 携带的 run/case 关联被归一化分支正确消费；
8. 既有 332 个 pytest 零修改全绿（OTLP 路径保留的直接验证）；
9. E2E：注册 trace-sdk 模式目标 → 发起评测 → Trace complete → 结果产出，
   全链路时延满足引擎等待窗（默认 30s deadline）。

端到端旅程：

```text
注册（bridge 模式）目标
  -> 发起评测（引擎登记 pending 关联 + trace_id 注入）
  -> Agent 桥接采集（metadata 带 run/case；flush 先于响应）
  -> file/Redis 事件流
  -> trace_sdk 接收器拉取 -> 归一化 -> merge -> COMPLETE
  -> 评测器消费 canonical Trace -> Result 锚定修订/哈希
```

## 参考

- 原设计：[ingestion-plan](ingestion-plan.md)、[external-target-plan](../run/external-target-plan.md) §Trace Correlation
- 现行实现：`src/agentgate/trace/`（receivers / normalizer / merge / completeness）
- 引擎轮询：`src/agentgate/run/core.py` `_resolve_trace`
- trace-sdk：`/Users/baibo/01-XunZhan/trace-sdk`（trace_sdk / trace_consumer / trace_server / db/schema.sql）
