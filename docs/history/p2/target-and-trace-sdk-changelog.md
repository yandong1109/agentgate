# P2 交付记录：评测对象管理 + Ticket-Approv-Agent + Trace 传输切换（trace-sdk）

| 项目 | 内容 |
|---|---|
| 日期 | 2026-09-04 |
| 分支 | `integration/p1-new` |
| 回退锚点 | tag `pre-target-p2`（评测对象管理改动前基线） |
| 测试证据基线 | 后端 pytest 373 passed / 前端 Vitest 20 passed / Playwright E2E 15 passed / vue-tsc 零错误 / CLI fallback 冒烟 gate: pass |

---

## 一、交付总览

本轮在 `integration/p1-new` 上交付三块能力（评审文档存档于评审人桌面目录）：

1. **评测对象管理（P2，REQ-001/002/003）**：注册、配置、版本化 Agent 目标
   （端点、认证、能力声明），含前端管理页与全链路测试；
2. **Ticket-Approv-Agent**：LangChain 架构 stub 示例被测 Agent，打通注册接口，
   后切换至 trace-sdk 遥测通道；
3. **Trace 传输方式切换（OTel → trace-sdk）**：设计文档评审合入 + G1 代码实施
   （"只换两头，保住中间"）。

## 二、提交清单（时间序）

| 提交 | 阶段 | 内容 |
|---|---|---|
| `00981e1` | S1 后端 | 评测对象注册模块 `src/agentgate/target/`（domain/repository/service/api）：注册（自动发布不可变 v1）、版本发布（content_sha256 内容哈希、留空继承）、双连通性测试（临时/已注册）、软删除（run 引用保护、slug 释放）；控制平面注册表动态合并（demo 硬编码 + DB 注册，同 id DB 优先，provider 故障回落 demo）；`/api/targets` 路由（envelope 响应）；安全红线（密钥字段 400 拒绝、只存 credential_ref、错误脱敏）；新表 `eval_target`/`eval_target_version` 纯增量。测试：L1 契约 11 例 + L2 FakeHttpAgent 全链路 13 例 |
| `2105d41` | S2 前端 | `views/targets/` 占位页重写（列表/统计/搜索/过滤/测试连接面板/软删除）；四步注册向导 `RegisterWizard.vue`；版本管理抽屉 `VersionDrawer.vue`（不可变版本、留空继承发布、按版本测试）；`api/targets.ts`/`types/target.ts` 扩展（`versions()` 保留，契约只增不改）。Vitest 组件测试 6 例 |
| `998026a` | S3 联动 | `task/api.py::_get_target_info` 切 target 服务数据源（修复原 `src.agentgate` 导入必失败的静默降级）；run store `ensureVersionExists` + datasets 页默认选择动态校正；新增 task 桥接 L2 测试 |
| `014c8fc` | S4 E2E | `tests/fake_agent_server.py` 独立假 Agent 进程（Playwright 第三 webServer）；`FakeHttpAgent` 支持固定端口；`targets.spec.ts` 三旅程（注册→评测闭环 / 死端口错误分类+脱敏 / 版本发布与 is_latest 迁移） |
| `82890be` | Agent | `src/Target-Agent/`：Ticket-Approv-Agent（chain.py LangChain 风格链路 stub、app.py Invoke 契约、telemetry.py OTLP 回退）；实测注册成功 + 全链路 Run completed |
| `eba0c35` | Agent 修复 | 工具 span 名必须是工具名本身（评估器按 `span.name` 匹配，`trace/merge.py:58` 直取 OTLP name 字段）；修正后工单数据集门槛 pass（1.0） |
| `50168e6` | 合并 | feature/target-registration 并入 integration/p1-new（S1-S4 全部交付，merge 干净无冲突） |
| `ddc1efa` | 设计文档 | Trace 传输方式切换评审稿合入：新增 `docs/trace/trace-sdk-integration-plan.md`（权威设计：范式对比、四鸿沟桥接、事件→NormalizedSpan 映射表冻结契约、灰度 G0-G3）；ingestion-plan/external-target-plan/demo-agent-plan 等 8 份文档通告与增补；台账追加决策条目（既有条目零改动）。评审过程文档：桌面 `Trace-SDK切换评审文档`、副本 `new-design/` |
| `66604bf` | G1 代码 | trace-sdk 接入（详见下节） |
| 本提交 | 记录 | 本交付记录文档 |

## 三、G1 trace-sdk 接入（`66604bf`）——只换两头，保住中间

**新增（生成/接收侧）**：

| 文件 | 职责 |
|---|---|
| `src/agentgate/trace/normalizer.py`（追加） | `normalize_trace_sdk_events` 事件归一化分支：span_type→SpanKind 映射（tool/retriever→TOOL，agent/chain/llm→AGENT）、metadata 关联（`agentgate.*` 键）+ pending resolver 兜底、TraceEvent→`agent.complete` terminal span + trace_complete/turn_complete/final_output/final_state 信号、UUID ID 放宽、ISO-8601→纳秒、observation/llm_request 独立 EVENT span |
| `src/agentgate/trace/receivers/trace_sdk.py` | file 模式接收器：offset 增量拉取、半行容错、幂等重放（批次哈希 + span 身份去重兜底）、`run_forever` 守护循环 |
| `src/agentgate/server/application.py`（修改） | `AGENTGATE_TRACE_SDK_FILE_ROOT` env 开关 + lifespan 守护线程（`AGENTGATE_TRACE_SDK_POLL_SECONDS` 轮询间隔） |
| `src/agentgate/contrib/agentgate_bridge.py` | Agent 侧桥接（自包含零依赖）：轻量 writer 产 trace-sdk file 后端格式 JSONL；traceparent trace_id 注入（32-hex，与 pending 关联精确匹配）；metadata 携带 run/case/turn/invocation 与 `agentgate.final_state.json`；write-through 满足 flush 及时性；多轮每轮独立 trace 靠 metadata 聚合 |
| `src/Target-Agent/app.py`（修改） | Ticket-Approv-Agent 切桥接模式（设置 root 时），未设置回退 OTLP |
| `tests/fake_agent_server.py`（修改） | 假 Agent 双模式（OTLP 存量 / trace-sdk 桥接） |
| `web/playwright.config.ts`（修改） | E2E 走 trace-sdk 通道（共享事件目录 env） |
| `tests/test_trace_sdk_normalizer.py` | L1 映射测试 33 例（冻结契约逐条） |
| `tests/test_trace_sdk_receiver.py` | L2 接收器测试 8 例（拉取→COMPLETE 收敛/重复幂等/半行/增量追加/孤儿拒绝） |

**零改动**（设计纪律验证）：`trace/merge.py`、`completeness.py`、`ordering.py`、
`service.py`、`storage/`、`run/core.py`、`run/targets/http.py`、全部评测器、
OTLP 接收器（灰度保留）、demo python_fn。

**实施中发现并修订的 3 处设计偏差**（已写入映射表 v0.2 留痕）：

1. final_state 改经 TraceEvent metadata 供信号——原设计"invoke 响应（适配器
   结果优先级）"在既有实现中未落地；
2. TraceEvent 须同时归一化为 terminal EVENT span——service.ingest 要求信号挂
   在已接受的 span 上（与 OTLP terminal span 模式对称）；
3. observation/llm_request 独立 EVENT span——原"附加为 attributes"方案在晚到
   场景会造成同 span 身份不同内容的伪冲突。

## 四、接口影响速查（团队同步用）

- **不变（照原设计文档执行）**：invoke 契约（请求/响应/头部/错误表）、
  pending_trace_correlation 关联机制、canonical Trace/merge/排序/幂等/冲突/
  修订/Result 锚定、评测器消费规则、数据集/注册/评测对象 API；
- **变化（遵照 `trace-sdk-integration-plan.md`）**：Agent 埋点（CallbackHandler +
  桥接）、遥测线格式（trace-sdk 事件 JSONL）、摄取入口（file/Redis 拉取，
  `POST /v1/traces` 过渡保留）、终态信号来源（TraceEvent + metadata）。

## 五、验收数据（最终全量）

| 层 | 结果 |
|---|---|
| 后端 pytest | **373 passed**（旧 332 零修改 + 新增 41：L1 映射 33 + L2 接收器 8） |
| 前端 Vitest | **20 passed**（含新增评测对象组件 6 例） |
| Playwright E2E | **15 passed**（demo/dataset 回归 12 + targets 三旅程走 trace-sdk 新通道 3） |
| vue-tsc / ESLint | 零错误 / 0 errors |
| 全链路实测 | Ticket-Approv-Agent（trace-sdk 通道）+ 工单数据集：Run completed，**gate pass 1.0（达到发布门槛）** |
| CLI fallback 冒烟 | 全新 DB `agentgate evaluate --version loan-agent-v2-fixed` → gate pass |

## 六、部署与环境变量（trace-sdk 通道）

```bash
# 后端（拉取接收器；两个进程的 root 必须一致）
AGENTGATE_TRACE_SDK_FILE_ROOT=/path/to/sdk-out
AGENTGATE_TRACE_SDK_POLL_SECONDS=1.0        # 可选

# 被测 Agent（桥接写事件；未设置时 Ticket-Agent 回退 OTLP）
AGENTGATE_TRACE_SDK_FILE_ROOT=/path/to/sdk-out
```

事件目录布局（trace-sdk file 后端约定）：`<root>/<project_id>/<run_id>/<trace_id>.jsonl`。

## 七、遗留与后续（G2+）

1. Redis 接收模式（跨机部署）与 Kafka（按需）；
2. 多轮用例实测（设计已知限制：轮级 trace 聚合，桥接每轮独立 TraceEvent）；
3. 技能路由评估器在 trace-sdk 路径恒不适用（可选桥接增强：metadata 补
   `selected_skill`）；
4. G0 外部前置项跟踪：trace-sdk 仓库 `trace_consumer/fields.py` 缺失、
   PG schema 未落 metadata/tags（file 模式不受影响）；
5. OTLP 接收器 G3 收口（当前标记保留，随时可回退）。

---

## 八、追加交付：任务管理接真链路（2026-09-04）

**需求**：评测入口从「发起评测·运行评估」扩展到「任务管理·创建任务·启动」，
最小改动复用原接口与数据。

**改动（后端 ~100 行，前端 0 行，数据模型 0 变更）**：

| 文件 | 改动 |
|---|---|
| `server/application.py` | 新增 `get_evaluation_service()` 全局访问器 |
| `task/api.py`、`task/scheduler.py` | 修复三处 `from src.agentgate...` 坏导入（src 布局下必失败且被吞——此前取数据集恒空、执行全为伪造数据） |
| `task/scheduler.py` `_execute_task` | **删除**硬编码 demo（苏州市调研样例）与伪造结果（85.0/模拟响应）；**替换为** `asyncio.to_thread(EvaluationService.launch(target_id, dataset_id, None, [evaluator_id]))` 真链路——与「运行评估」同一入口；从 `engine.report` 映射 TaskRun 统计（completed/passed/failed/avg_score 0-100）与逐用例 CaseExecution（真实评分与评估器结果摘要）；Run 未完成/异常 → 任务 FAIL 留痕 |
| `tests/task/test_real_execution.py`（新增） | 3 个集成测试：真链路成功（demo 目标）/ 死端点失败 / 未知评估器失败 |

**复用要点**：任务表 `target_id` 存的正是 `versions()` 的版本键（launch 的
version 参数）、`dataset_id` 传 None 自动取最新 published 版本——数据天然对齐，
零 schema 变更；真实 Run 自动出现在运行记录/结果报告页。

**验收**：后端 376 passed（旧测试零修改）；E2E 15；实测「创建→启动→调度执行
（10 秒扫描）」走 trace-sdk 通道（Ticket-Approv-Agent + 工单数据集）：任务
SUCCESS、2/2 用例通过、avg 100.0（真实报告值，非伪造 85.0）、CaseExecution
摘要为真实评估结果。

**已知限制**：launch 阻塞式执行，长数据集任务占用调度器单循环（POC 可接受）；
任务详情页跳转结果报告按钮为 P2 增强（需 TaskRun 加 external_run_id 列）。
