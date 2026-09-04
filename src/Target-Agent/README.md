# Ticket-Approv-Agent

基于 LangChain 架构的工单审批 Agent（接口打通版），对接 AgentGate「评测对象注册」。

## 架构

```
chain.py          LangChain 风格链路（本地 Runnable shim，可替换为真实 langchain_core）
                  classify_ticket | decide_approval | build_state
app.py            HTTP 服务：POST /invoke（AgentGate Invoke 契约）+ GET /health
telemetry.py      OTLP 遥测导出：AgentGate /v1/traces（含 trace 完整性信号）
```

- **stub 模式**：`chain.py` 用确定性规则模拟审批决策（高风险/金额 > 50000 → 转人工；否则自动批准），无需 LLM Key 即可联调。真实实现时仅需替换 `decide_approval` 内部为 LLM 调用，链路组装与接口不动。
- **遥测闭环**：评测运行要求 Agent 把 OTLP trace 回传 AgentGate（评估器消费的是 trace，不是 invoke 响应）。本 Agent 的 terminal span 携带 `agentgate.trace.complete` 等完整性信号，评测链路可真实闭环。

## 运行

```bash
# 依赖复用 agentgate 的 venv（fastapi/uvicorn/pydantic）
cd /Users/baibo/3-ZhuGanCang/agentgate
.venv/bin/python src/Target-Agent/app.py

# 可选环境变量
#   TICKET_AGENT_PORT        监听端口，默认 8090
#   AGENTGATE_OTLP_ENDPOINT  AgentGate OTLP 接收地址，默认 http://127.0.0.1:8010/v1/traces
```

## 在「评测对象」页注册（向导填法）

| 向导步骤 | 填写 |
|---|---|
| 基本信息 | 展示名称：`Ticket-Approv-Agent`；类型：Agent |
| 端点与认证 | HTTP 端点：`http://127.0.0.1:8090/invoke`；凭证引用：留空（本 Agent 不校验 Authorization） |
| 能力声明 | `ticket_approval`（tool）；`ticket_review`（tool） |
| 测试并注册 | 点「测试连接」应显示连接成功 → 「确认注册」 |

注册后 `GET /api/versions` 中会出现 `ticket-approv-agent-v1`，可在「发起评测」的 Agent 选择器中选用。

## 对端契约速查（Agent 必须满足的最小集合）

1. `POST` + JSON 请求/响应（响应 Content-Type 含 `json`）
2. 响应 200，body 必含 `output` 与 `final_state`
3. trace 回传：`traceId` = 请求头 `traceparent` 的 trace-id，含完整性 terminal span

## 注意

- 用默认 loan 数据集对本 Agent 跑评测：Run 会正常完成（接口闭环验证），但门槛结果取决于数据集期望与 Agent 行为是否匹配（loan 数据集期望 `credit_inquiry`/`request_human_review` 等工具），属预期现象；配对的工单数据集待后续导入。
