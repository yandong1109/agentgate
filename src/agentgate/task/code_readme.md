# 任务模块代码文档 (V5)

## 1. 模块概述

任务模块是 AgentGate 评测系统的任务调度入口，负责：
- 管理评测任务的编排（创建/启动/停止）与任务侧执行留痕
- 调度执行：**复用 `EvaluationService.launch()` 真链路**（与「发起评测·运行评估」
  同一入口）执行测评集全部用例——快照固化、调用评测对象、等待 Trace、
  运行评估器、产出门槛结果（2026-09 起替换此前的硬编码 demo 与伪造结果）
- 将真实报告映射为 TaskRun 统计与 CaseExecution 逐用例记录

## 2. 目录结构

```
src/agentgate/task/
├── __init__.py           # 模块导出
├── domain.py             # 领域模型（TaskStatus, AgentType, EvalTask 等）
├── agent.py              # AgentExecutor 抽象类和实现
├── evaluator.py          # Evaluator 抽象类和实现
├── service.py            # SchedulerService 和 TaskExecutionService
├── repository.py         # SQLAlchemy 模型和仓储
├── api.py                # FastAPI 路由
├── scheduler.py          # BackgroundScheduler（真链路执行体）
├── evaluation_center.py  # 评估中心客户端
└── code_readme.md        # 本文件
```

## 3. 核心概念

### 3.1 TargetAgent vs AgentExecutor

- **TargetAgent**：表示智能体的领域实体（存储在数据库中）
- **AgentExecutor**：任务运行时的执行抽象

工厂类 `TargetAgentFactory.create(agent_type, config)` 根据 `TargetAgent` 的配置创建 `AgentExecutor` 实例。

### 3.2 智能体类型

| 类型 | 说明 |
|------|------|
| SKILL | 技能型智能体 |
| REMOTE_AGENT | 远端 Agent 服务 |
| AGENT_WORKFLOW | 多步骤工作流智能体 |

### 3.3 评估器类型

| 类型 | 说明 |
|------|------|
| RULE | 规则评估器（JSON 校验、正则匹配等） |
| LLM | LLM 评估器（使用大语言模型） |
| COMPOSITE | 复合评估器（组合多个评估器） |

### 3.4 任务状态流转

```
NEW → PENDING → RUNNING → SUCCESS/FAIL/TERMINATED
```

| 状态 | 说明 | 允许的转换 |
|--------|-------------|---------------------|
| NEW | 新建 | PENDING |
| PENDING | 待执行 | RUNNING, TERMINATED |
| RUNNING | 执行中 | SUCCESS, FAIL, TERMINATED |
| SUCCESS | 执行成功 | - |
| FAIL | 执行失败 | - |
| TERMINATED | 人工终止 | - |

## 4. 领域模型

### 4.1 实体

- **TargetAgentEntity**：智能体实体
- **Dataset**：包含测试用例的评测集
- **Case**：多轮对话测试用例
- **EvaluatorEntity**：评估器配置
- **EvalTask**：评测任务
- **TaskRun**：任务执行记录
- **CaseExecution**：单个用例执行记录
- **EvaluationResultEntity**：评估结果

### 4.2 值对象

- **TraceInfo**：智能体执行 trace 信息
- **EvaluationResult**：评估结果（得分、是否通过、原因、详情）

### 4.3 快照

- **TargetSnapshot**：TargetAgent 配置快照
- **DatasetSnapshot**：包含所有用例的 Dataset 快照
- **EvaluatorSnapshot**：评估器配置快照

## 5. 智能体执行器

### 5.1 AgentExecutor（抽象基类）

```python
class AgentExecutor(ABC):
    def initialize(self) -> None: ...
    def send_query(self, question: str) -> str: ...
    def get_trace(self) -> TraceInfo: ...
    def close(self) -> None: ...
```

### 5.2 实现类

- **LocalAgentExecutor**：用于测试环境
- **SkillAgentExecutor**：用于 SKILL 类型智能体
- **RemoteAgentExecutor**：用于 REMOTE_AGENT 类型智能体
- **WorkflowAgentExecutor**：用于 AGENT_WORKFLOW 类型智能体

### 5.3 工厂类

```python
class TargetAgentFactory:
    @staticmethod
    def create(agent_type: str | AgentType, config: dict) -> AgentExecutor:
        ...
```

## 6. 评估器

### 6.1 Evaluator（抽象基类）

```python
class Evaluator(ABC):
    def set_config(self, config: dict) -> None: ...
    @abstractmethod
    def calculate(self, case_execution: CaseExecution) -> EvaluationResult:
        ...
```

### 6.2 实现类

- **RuleEvaluator**：基于规则的评估（contains、not_contains、regex、equals）
- **LLMJudgeEvaluator**：基于 LLM 的评估
- **CompositeEvaluator**：使用权重组合多个评估器

### 6.3 工厂类

```python
class EvaluatorFactory:
    @staticmethod
    def create(evaluator_type: str | EvaluatorType, config: dict) -> Evaluator:
        ...
```

## 7. 服务

### 7.1 SchedulerService

处理任务生命周期管理：
- `create_task()`：创建新的评测任务
- `start_task()`：启动任务（NEW → PENDING）
- `stop_task()`：停止任务（PENDING/RUNNING → TERMINATED）

### 7.2 TaskExecutionService

处理任务执行：
- `execute_task()`：执行评测任务
- `execute_case()`：执行单个测试用例
- `cancel_task()`：取消正在运行的任务

### 7.3 BackgroundScheduler（真链路执行体，scheduler.py）

后台调度循环（默认 10 秒扫描 PENDING 任务），`_execute_task` 执行流程：

```
PENDING 任务
  → TaskRun 置 RUNNING
  → asyncio.to_thread(EvaluationService.launch(
        target_id,   # 版本键，如 "ticket-approv-agent-v1"（versions() 的 id）
        dataset_id,  # 数据集 ID（自动取最新 published 版本）
        evaluator_ids=[task.evaluator_id],
    ))
  → 真实 Run（完整评测闭环：快照固化/invoke/等 Trace/评估/门槛）
  → 从 engine.report 映射：
       TaskRun.completed/passed/failed_cases、avg_score（0-100）
       CaseExecution 逐用例（passed、score、评估器结果摘要）
  → 任务与 TaskRun 置 SUCCESS；任何异常 → 双双置 FAIL（错误留日志）
```

要点：
- **真实 Run 同时落在运行记录/结果报告页**（与「发起评测」产物同源可查）；
- launch 为阻塞调用（每用例含 Trace 等待），经 `to_thread` 不阻塞调度循环；
- 评测服务经 `agentgate.server.application.get_evaluation_service()` 获取
  （注意：不是 `src.agentgate...`——此前三处该形态的导入在 src 布局下必失败，
  已全部修复）；
- 任务侧快照（target/dataset/evaluator_snapshot 表）继续作为任务系统审计
  留痕；评测语义的权威快照在真实 Run 的 RunSnapshot 中（双留痕并存）。

## 8. 数据库模型

参见 `repository.py` 中的 SQLAlchemy 模型：
- `TargetAgentModel`：target_agent 表
- `DatasetModel`：dataset 表
- `CaseModel`：case_table 表
- `EvaluatorModel`：evaluator 表
- `EvalTaskModel`：eval_task 表
- `TaskRunModel`：task_run 表
- `CaseExecutionModel`：case_execution 表
- `EvaluationResultModel`：evaluation_result 表
- 快照模型：target_snapshot、dataset_snapshot、evaluator_snapshot

## 9. API 端点

| 方法 | 端点 | 说明 |
|--------|----------|-------------|
| POST | /api/v1/tasks | 创建任务 |
| GET | /api/v1/tasks | 查询任务列表 |
| GET | /api/v1/tasks/{task_id} | 查询任务详情 |
| POST | /api/v1/tasks/{task_id}/start | 启动任务 |
| POST | /api/v1/tasks/{task_id}/stop | 停止任务 |
| POST | /api/v1/tasks/{task_id}/rerun | 重新执行任务 |
| DELETE | /api/v1/tasks/{task_id} | 删除任务 |
| GET | /api/v1/tasks/{task_id}/runs | 查询执行记录列表 |
| GET | /api/v1/runs/{run_id} | 查询执行记录详情 |
| GET | /api/v1/runs/{run_id}/executions | 查询用例执行列表 |
| GET | /api/v1/executions/{execution_id} | 查询用例执行详情 |
| POST | /api/v1/executions/{execution_id}/rerun | 重新执行用例 |

## 10. 测试

使用 pytest 运行测试：

```bash
pytest tests/task/ -v
```

关键测试：`tests/task/test_real_execution.py`——任务真链路集成测试
（创建 → 启动 → 真实执行 → 断言统计/逐用例结果/真实 Run 落库；含失败路径
与未知评估器路径，使用 demo 目标零外部依赖）。

## 11. 依赖

- Python 3.10+
- FastAPI
- SQLAlchemy
- Pydantic（来自父模块）
