# matches_json_schema 大小/深度保护与预检 API 设计计划

> 本文件是 AgentGate 评估器在 `matches_json_schema` 算子上补齐资源保护、并统一前后端
> schema 校验入口的增量设计，是本增量的**原生设计权威源**（非翻译件）。
> 行为契约与验收状态以本文件、`docs/evaluator/implementation-plan.md` 及
> `docs/progress.md` 为最终裁决。
> 模块所有权边界以 `docs/architecture-review-ledger.md` 为准；本文件不改变所有权，
> 只在 evaluator 所有权内新增行为与对外契约。

## 修改级别

**M 级**。触犯不变量 #2「Evaluator 拥有判断行为」与 #12「UI/API 层委托给应用服务，不复制
领域规则」的边界——但**不变量本身不变**，只是在 evaluator 所有权内新增 size/depth 校验
行为，并新增一个委托式预检 API 契约。流程：先与用户确认方向（本文档）→ implementer 实现
→ 全量质量门 → reviewer 评审（最多 2 轮）。

## 1. 目标

`matches_json_schema` 算子与 `MatchesJsonSchema` Condition 已在 `goal/p1-demo` 实现，
但 `docs/evaluator/implementation-plan.md` §Security and Resource Rules 要求的两条输入
保护尚未落地：

> - Reject schemas over a configured serialized-size limit.
> - Apply bounded nesting/depth checks before accepting untrusted schemas.

grep 确认 `src/agentgate/evaluator/` 下**无任何 schema 输入的 size/depth 限制**：operator
的 `_MAX_VIOLATIONS=20` / `_MAX_REASON_LENGTH=500`（`operators/json_schema.py`）是对**评估
输出**（违规摘要）的限制，与对**输入 schema** 的资源保护是两件事，互不替代。

本增量达成：

1. 在 evaluator 校验层加入 schema 序列化大小上限与嵌套深度上限检查，作为 `check_schema`
   之前的快速闸门，防止 CWE-674（Uncontrolled Recursion）类 DoS 与超大 schema 拖垮 Run。
2. 把 limit 定义为后端单一源、可经环境变量覆盖，**前端不持有任何 limit 值、不做任何 schema
   语义/size 判断**。
3. 新增一个预检 API（方式 b）：前端编辑 `matches_json_schema` 时实时委托后端跑同一校验函数
   并回显结构化错误，前后端校验逻辑单一源、永不漂移。
4. 明确校验时序与所有权硬约束：草稿可存语义非法的 schema、Run 前才拒（现有设计不变更）。

本计划**只写设计/契约/验收标准，不含完整实现代码**。

## 2. 设计要点覆盖对照

| 任务要求的设计要点 | 本文件章节 |
| --- | --- |
| 1. limit 单一源与可配置（含默认值论证 + 可配置入口优先级） | §3、§4 |
| 2. 预检 API 契约（方式 b：请求/响应结构） | §5 |
| 3. 校验时序与所有权约束（不变量 #2/#12） | §6 |
| 4. 前端接入方式（基础 UI 不变 + 预检钩子 + 降级） | §7 |
| 5. 测试策略 | §9 |

## 3. limit 单一源与可配置

### 3.1 单一源位置

limit 常量定义在 **`src/agentgate/evaluator/validation.py`** 模块级，作为唯一权威源：

- 校验函数 `validate_json_schema`（§6.3 新增的公开入口）读取这两个 limit；
- 预检 API 与 Run 前校验**调用同一函数**，因此 limit 天然单一源；
- 前端**不复制 limit 值**，仅通过预检 API 回显后端结果（§7）。

### 3.2 可配置入口与优先级

```
优先级（高 → 低）：
  环境变量  >  模块默认值
```

- 环境变量名（建议）：
  - `AGENTGATE_JSON_SCHEMA_MAX_DEPTH`
  - `AGENTGATE_JSON_SCHEMA_MAX_SERIALIZED_SIZE`
- 解析规则：启动时读取并解析为正整数；解析失败或缺省时回退模块默认值；非法值不静默吞掉，
  记一条启动告警并回退默认（不阻塞启动）。
- 不引入数据库/配置文件层；环境变量是当前阶段唯一可配置入口，足够覆盖"部署侧调参"需求。
  若后续需要租户级配置，须另起契约讨论，不得在本增量私扩存储模型。

> 注：`server/application.py` 的 OTLP 入口已用 `os.getenv(..., str(default))` 模式做同类
> 可配置（见该文件 L357-363 `AGENTGATE_OTLP_MAX_REQUEST_BYTES`）。本增量沿用同一模式，
> 保持配置入口风格一致。

### 3.3 校验方式

| 维度 | 计算方式 | 复用既有设施 |
| --- | --- | --- |
| 大小 | `len(canonical_json(schema).encode("utf-8"))` 字节数 | `domain/base.py::canonical_json`（`allow_nan=False`、`sort_keys=True`、`separators=(",",":")`、`ensure_ascii=False`），与 `content_sha256` 同序列化口径，对齐 implementation-plan「serialized-size limit」措辞 |
| 深度 | 对 schema 容器（dict/list）做**显式栈迭代**计数最大嵌套层数；标量值不增加深度 | 不依赖 jsonschema 库（库无内置深度保护，见 §4） |

深度检查必须用**显式栈/队列迭代**而非递归，否则校验自身会在恶意深嵌套上触发
`RecursionError`，与要防的风险同类。计算只统计 schema **结构嵌套深度**（容器层层包裹），
**不**统计 `$ref`/`$dynamicRef` 解析深度（远程 $ref 已在另一闸门禁止，本地 `$defs`/片段引用
的解析深度由库在 `check_schema`/验证阶段处理，不在本闸门职责内）。

## 4. 推荐默认值与依据

> 依据来自 `.tavily/json-schema-size-depth-limits.md`（已联网核验，复用周期：稳定；若
> jsonschema 库后续引入内置深度保护需复核）。

### 4.1 深度 `max_depth` 默认 **64 层**

依据：

- **jsonschema 库无内置递归深度保护**：验证深嵌套 schema 时依赖 Python
  `sys.getrecursionlimit()`（默认 1000），且每层 descend/`iter_errors`/`allOf` 等消耗多个栈帧，
  实际可承受深度远小于 1000（issue python-jsonschema/jsonschema#847 实测深嵌套 `anyOf`/`allOf`
  会抛 `RecursionError: maximum recursion depth exceeded`）。
- 风险类型 **CWE-674（Uncontrolled Recursion）**，可被恶意深嵌套 schema 触发 DoS。
- 对照：orjson 3.11.6（CVE-2025-67221 修复）在 JSON **解析**层引入 1024 层深度限制；
  jsonschema 库在**验证**层无对应保护 → 必须由调用方（AgentGate validation 层）自行加。
- 真实业务 schema 嵌套极少超 20–30 层；**64 既远超合理需求，又远离栈溢出边界**。

校验时机：提交前对 schema 做静态递归深度计数（不触发库验证即可算），超限即拒。

### 4.2 大小 `max_serialized_size` 默认 **256 KB = 262144 字节**

依据：

- 业界参考跨度 1 KB–10 MB：Azure API Management 4 MB、Broadcom Layer7 API Gateway 10 MB
  （`json.schemaCache.maxDownloadSize` 默认 10485760 字节），二者偏 API gateway 处理第三方大
  schema 场景；Cloudflare 针对请求体阈值过小不适用。
- AgentGate 场景特点：schema 是 `DatasetVersion` 配置的一部分（存 SQLite TEXT），非高频 API
  校验；用户可控但需防滥用与栈溢出。
- **256 KB 容纳几乎所有合理业务 schema**（复杂业务 schema 几十 KB 常见），又远低于拖垮系统
  的级别；是"配置型 schema"而非"网关型大 schema"场景下的合理上界。

校验方式：用 `canonical_json(schema)` 字节数（对齐 implementation-plan「serialized-size
limit」）。

### 4.3 默认值性质

以上两个默认值（64 层 / 256 KB）是本计划的**建议值**，最终值由用户确认（见 §11 决策点）。
确认后写入 `validation.py` 作为模块默认；环境变量仍可覆盖。

## 5. 预检 API 契约（方式 b）

用户已选定预检获取方式为**方式 b：预检 API**——前端编辑时实时委托后端校验并回显错误，
前端零校验逻辑。本节定义该 API 契约。

### 5.1 端点

```
POST /api/json-schema/validate
```

- **动词子路径命名**（非名词资源）。本接口作用是**非 CRUD 的纯校验动作**：不操作已有资源状态、
  无副作用、不持久化、schema 无持久化 id——因此不宜套用名词资源 CRUD 范式，而用动词子路径
  `validate` 直接表达意图。
- 依据见 `.tavily/schema-validate-endpoint-naming.md`（已联网核验，复用周期：稳定）：
  - **Google AIP-136**：标准方法优先，自定义动词方法用于"难以用标准方法完成的功能"，校验正当属此类；
  - **Clean Code 三原则**：`validate` intention-revealing（一眼看出"校验"，无需绕"创建校验实例=校验"），
    且不过度建模（不为 REST 合规硬造 `validations` 假资源实体）；
  - **与现有代码库一致**：`server/application.py` 已有动词子路径先例 `POST /api/datasets/{id}/copy`、
    `POST /api/runs/{run_id}/cases/{case_id}/rerun`，本端点沿用同一风格。
- 单数 `json-schema` 作动作限定词（非集合），类比现有单数命名空间 `/api/overview`；不用复数
  `json-schemas`，以免暗示存在 `GET /api/json-schemas` 资源集合。
- 前缀 `/api` 与既有端点一致；端点定义在 `server/application.py`。

### 5.2 请求

```jsonc
{
  "json_schema": <object | string>,            // 必填。可为已解析对象，或 JSON 文本（后端 json.loads）
  "instance_mode": "structured" | "json_text"  // 可选，默认 "structured"
}
```

- `json_schema` 允许传 string（`object | str` union）：预检是**独立校验通道**，调用方（PR3
  预检钩子）可传原始文本，由后端 `json.loads` 并在解析失败时返回 `input_parse_error`，使后端
  成为「能否解析」的权威。注：PR1 的 `setSchema` 两道闸已在**持久化路径**上 `JSON.parse`
  （§7.2），故 PR3 钩子亦可直接传已解析的 object——两种传法后端均支持，API 不强制。
- `instance_mode` 透传给校验函数，使预检与 Run 时语义一致（虽然 size/depth 不依赖
  instance_mode，但校验函数签名统一）。

Pydantic 请求模型（在 `server/application.py` 新增）：

```
class ValidateSchemaRequest(BaseModel):
    json_schema: object | str          # union，运行时 isinstance 分支
    instance_mode: Literal["structured","json_text"] = "structured"
```

### 5.3 响应

**语义约定**：预检是"返回校验结果"，不是"创建资源"。schema 不合法是**业务结果**而非请求
错误，因此用 HTTP 200 + `valid:false` 表达，而非 4xx（请求本身合法且被正确处理）。仅当请求
体本身不合法（字段缺失/类型错）才用 422。

成功（schema 合法）：

```json
{ "valid": true }
```
HTTP 200。

失败（schema 不合法，校验完成但被拒）：

```json
{
  "valid": false,
  "errors": [
    {
      "code": "depth_exceeded",
      "message": "schema 嵌套深度 72 超过上限 64",
      "limit": 64,
      "actual": 72
    }
  ]
}
```
HTTP 200。

`errors` 为数组（同一 schema 可能同时触发多条，但实现上按短路顺序返回首个命中的闸门错误
即可；如需全量可扩展）。错误码清单：

| code | 触发条件 | 额外字段 |
| --- | --- | --- |
| `input_parse_error` | `json_schema` 为字符串但无法 `json.loads` | — |
| `unsupported_draft` | `$schema` 声明且非 2020-12 | `declared` |
| `remote_ref_forbidden` | 含 `http://`/`https://`/`file://` 的 `$ref`/`$dynamicRef` | `ref` |
| `size_exceeded` | `canonical_json` 字节数超限 | `limit`, `actual` |
| `depth_exceeded` | 容器嵌套深度超限 | `limit`, `actual` |
| `invalid_schema` | `Draft202012Validator.check_schema` 失败 | `message`（已脱敏） |

**不暴露原始库异常**（implementation-plan §Rules to Avoid Design Drift #11「Do not expose raw
validation-library exceptions directly through the API」）。`invalid_schema.message` 取
`SchemaError.message` 并做长度截断（与 operator 输出限制同精神），不带堆栈/内部路径。

### 5.4 归属与委托链（不变量 #12）

```
server/application.py   预检端点（透传：请求模型 ↔ 响应模型；不写校验规则）
        │  调 service.validate_json_schema(json_schema, instance_mode)
        ▼
control_plane/service.py  EvaluationService.validate_json_schema（应用服务方法）
        │  构造临时 MatchesJsonSchema 或直接调 evaluator 暴露函数；不复制规则
        ▼
evaluator/validation.py  validate_json_schema(schema, instance_mode)  ← 单一逻辑源
        ▲
        │  Run 前 _validate_json_schema_condition 也调本函数
run/core.py::validate_evaluation_plan
```

- server 层只做 HTTP ↔ 调用 转换，**不**内联 draft/size/depth 规则。
- 应用服务 `EvaluationService.validate_json_schema` 只委托，不复制领域规则。
- 校验逻辑只存在于 `evaluator/validation.py`，Run 前校验与预检 API 走**同一函数**——这是
  "前后端校验永不漂移"的结构保证，不靠纪律。

## 6. 校验时序与所有权约束

### 6.1 现有时序（本增量不变更）

| 时机 | 入口 | 做什么 | 是否做 schema 语义校验 |
| --- | --- | --- | --- |
| 草稿保存 | `case/service.py::save_case`（L129-144） | 仅 `DatasetVersion.model_validate`（Pydantic 类型层：顶层 object + `canonical_json` 的 `allow_nan=False` 兜底）；`content_sha256` 置空 | **否** |
| 发布草稿 | `case/service.py::publish_draft`（L182-185）→ `case/validation.py::validate_dataset_version` | 结构 well-formed（用例/轮次/期望 ID 唯一、工具不重叠等） | **否**（只做结构） |
| Run 前 | `run/core.py` L58 `validate_evaluation_plan` → `evaluator/validation.py::_validate_json_schema_condition` | draft/远程$ref/`check_schema` | **是**（本增量在此加 size/depth） |
| 编辑时（新增） | 预检 API → `validate_json_schema` | 同 Run 前函数 | **是**（实时回显） |

**"草稿可存语义非法的 schema、Run 时才拒"是现有设计**，本增量**不变更该时序**。理由：
- 所有权硬约束（不变量 #2）：schema 语义校验属 evaluator；`case/` 不能做（`case/validation.py`
  只做结构 well-formed，见该文件——它检查 ID/名称/工具重叠，不碰 schema 语义）。
- 若要让草稿保存/发布就拒语义非法 schema，等于把 schema 语义下沉到 case 层，违反 #2，需另起
  契约变更讨论，不在本增量范围。

### 6.2 校验顺序（在 `validate_json_schema` 内）

按"先廉价新闸门、后昂贵库调用"排列，使恶意输入在触发 `check_schema` 的潜在 RecursionError
前即被拒：

> 注：size 闸门的 `canonical_json` 内部 `json.dumps`/`thaw_json` 亦是递归实现，对 depth≥~998（逼近 `sys.getrecursionlimit`）的对抗性 schema 会在迭代 depth 闸门前先抛 `RecursionError`；该极端尾部由 size 闸门 `try/except RecursionError` 兜底返 `depth_exceeded`，迭代 depth 闸门保护该天花板之下的深度（65–997）。

1. `input_parse_error`（仅预检 API 入口：string → json.loads）
2. `unsupported_draft`（`$schema` 声明检查，现有逻辑）
3. `size_exceeded`（`canonical_json` 字节数，新增）
4. `depth_exceeded`（显式栈计数，新增）
5. `remote_ref_forbidden`（`_find_remote_ref`，现有逻辑）
6. `invalid_schema`（`Draft202012Validator.check_schema`，现有逻辑）

> size 在 depth 之前：size 是一次序列化 O(n)，可先拒超大；depth 是一次栈遍历 O(n)，再拒过深。
> 两者均在 `check_schema` 之前，保证深嵌套/超大 schema 不会把库的 self-check 拖到栈溢出。

### 6.3 单一逻辑源：`validate_json_schema` 公开函数

在 `evaluator/validation.py` 暴露公开函数（契约签名，非实现）：

```
def validate_json_schema(schema: Mapping[str, Any], instance_mode: str) -> list[SchemaIssue]:
    """对单个 JSON Schema 跑 §6.2 全部闸门。返回 issue 列表；空列表=合法。"""
```

- `SchemaIssue`（领域内值对象，在 `evaluator/validation.py` 或 `evaluator/models.py` 定义）：
  `code: str`、`message: str`、可选 `limit: int|None`、`actual: int|None`、`ref: str|None`、
  `declared: str|None`。
- **Run 前路径**：`_validate_json_schema_condition(condition)` 改为调用 `validate_json_schema`
  （从 condition 取 `json_schema.to_dict()` 与 `instance_mode`），若返回非空则 raise `ValueError`
  （保持现有函数签名/异常语义不变，Run 前仍以 ValueError 中止计划）。
- **预检 API 路径**：`EvaluationService.validate_json_schema` 调同一函数，把 `list[SchemaIssue]`
  转成 §5.3 的响应体。

> 设计选择（返回 issues 列表而非 raise）：Run 前 需要 raise 以中止计划；预检 API 需要结构化
> 列表以回显。返回列表让两者各取所需，单一逻辑源不分裂。`_validate_json_schema_condition`
  在内部把非空列表转成 ValueError，是"消费方式"差异，不是"逻辑分裂"。

### 6.4 所有权自查（不变量 #2/#12）

- **#2 Evaluator 拥有判断行为**：size/depth/draft/ref/check_schema 全部在 `evaluator/`
  内；`case/` 不新增任何 schema 语义。✓
- **#12 UI/API 层委托给应用服务，不复制领域规则**：server 端点只做请求/响应转换；
  `EvaluationService.validate_json_schema` 只委托；规则只在 `evaluator/validation.py`。✓
- 预检 API 是"编辑期反馈通道"，**不改变** Run 前校验的权威性：即使预检通过，Run 前仍会再跑
  同一函数（防绕过、防草稿在预检后被改）。预检失败也不阻止保存（§7.3 降级）。

## 7. 前端接入方式

### 7.1 前端现状（PR1 已补齐编辑控件）

> PR1（分支 `feat/web-json-schema-condition`，提交 `feat(web): enable matches_json_schema
> condition editing`）已落地 `matches_json_schema` 的前端基础 UI，作为独立增量先于本计划合入。
> 以下描述的是 **PR1 合入后的前端状态**，本计划据此对齐。

- `web/src/types/dataset.ts`：`Condition` 已含 `matches_json_schema` 分支，带
  `json_schema: JsonObject` + 可选 `instance_mode?: 'structured' | 'json_text'`。
- `web/src/components/dataset/ExpectationEditor.vue`：`condition()` 工厂已覆盖该 kind
  （返回 `{ kind, json_schema: {}, instance_mode: 'structured' }`）；下拉选项含「JSON Schema 校验」；
  动态表单渲染 textarea + `instance_mode` 下拉；并有 `v-else` 兜底「未知条件类型」。
- 因此本增量（PR2）的**前端范围 = 零改动**：PR1 已补齐编辑控件，本增量只做后端（§5 预检 API +
  §6 校验函数 + §9 测试）。预检钩子（把 `setSchema` 两道闸的产物经防抖送后端预检、回显、降级）
  属 **PR3** 范围，在 PR2 后端上线后另起增量。

### 7.2 编辑控件与两道闸（PR1 已实现，本增量不改）

PR1 在 `ExpectationEditor.vue` 内，当 `row.condition.kind === 'matches_json_schema'` 时已渲染：

- 一个 schema 文本框（`el-input` textarea）：以 JSON 文本形式编辑，经 `setSchema(row, value)`
  处理后写回 `row.condition.json_schema`；
- 一个 `instance_mode` `el-select`：`structured` / `json_text`，默认 `structured`。

`setSchema` 实现**两道闸**（PR1 既定产出，本计划据此对齐，不另改）：

1. **JSON 格式闸**：`JSON.parse(value)` 失败 → 置 `schemaErrors` =「JSON 格式错误：…」，不写回；
2. **顶层对象闸**：解析结果为 `null` / 非 object / 数组 → 置 `schemaErrors` =「JSON Schema 顶层
   必须是对象」，不写回；
3. 两闸均过 → `row.condition.json_schema = parsed`，即写回为 **object**（非 string）。

**为何前端必须把文本框内容 parse 成 object（两道闸正当性）**——这与本计划初稿"前端不做格式判别、
原样存 string 由后端解析"的取向相反；PR1 采纳两道闸的做法更正确，理由如下：

- **持久化路径的类型契约要求 object**：草稿保存走 `addCase` / `updateCase`
  （`server/application.py` 的 `POST/PUT /datasets/{id}/drafts/cases`），请求体经 Pydantic `Case` →
  `MatchesJsonSchema.json_schema` 字段类型是 `FrozenJsonObject`（`domain/base.py`：实现 `Mapping[str, Any]`，
  `__init__` 对顶层非 Mapping 输入无法 `.items()`；`freeze_json` 对 string 走 scalar 分支，但顶层 schema
  必须是对象才能构造 `FrozenJsonObject`）。即后端反序列化层就要求 `json_schema` 是**对象**而非 string
  ——前端若原样存 string，请求会被 Pydantic 拒（422），根本无法保存草稿。
- 因此两道闸是**"构造合法 condition 对象的类型转换必要条件"**，不是复制领域规则：它只保证
  `row.condition.json_schema` 是一个可被 `FrozenJsonObject` 接受的 plain object，**不碰任何 schema 语义**
  （draft / `$ref` / `check_schema` / size / depth 一概不判）——这些语义判断仍 100% 在
  `evaluator/validation.py`（§6）。前端两道闸 ≈ 表单"先把文本 parse 成类型正确的值再提交"，与日期
  选择器产 Date、数值输入产 number 同性质，是 UI 的**值塑形**，不是**判断行为**。
- **预检 API 与持久化的区分**：预检 API 的 `json_schema` 字段仍可接受 string（§5.2：`object | str`，
  后端先 `json.loads`），因为预检是独立校验通道、不必经 `FrozenJsonObject`；但**持久化路径**要求 object。
  两道闸服务的是持久化路径，预检服务的是编辑期语义反馈，互不替代。

> 不变量 #12 自查：两道闸不复制 evaluator 的 schema 语义判断；UI/API 层对 schema **语义**仍零逻辑，
> 全部委托后端。两道闸属类型塑形，与 #12「UI/API 层委托给应用服务，不复制领域规则」不冲突。

### 7.3 预检钩子与降级（PR3 范围，PR2 不实现）

> 本节描述 PR1 已补控件 + PR2 后端预检上线后，PR3 要接入的预检钩子。PR2 不含任何前端改动。

- **触发**：schema 文本框变更，经防抖（约 300–500ms）后调 `api.validateSchema(...)`。
  （PR1 的 `setSchema` 两道闸即时生效、不防抖；预检是两道闸通过后再异步送后端做**语义**校验。）
- **回显**：预检返回 `valid:false` 时，在文本框下方展示 `errors[0].message`（按 code 可给
  i18n 友好文案，但 limit/actual 等数值来自后端，前端不硬编码数值）。
- **降级（关键）**：预检 API 不可达/超时/抛错时，**前端仍允许保存草稿**——不阻断编辑流程。
  理由：草稿本就允许存语义非法 schema（§6.1），最终裁决在 Run 前后端校验。预检只是体验优化，
  不是安全边界；安全边界永远在后端 `validate_evaluation_plan`。
- 前端**不缓存 limit 值**、**不本地复算 size/depth**：任何"这个 schema 多大/多深"的判断都
  必须问后端，否则前后端会漂移。

### 7.4 前端 API 封装（PR3 范围，PR2 不实现）

> `validateSchema` 方法与 `SchemaIssue` 前端镜像属 PR3；PR2 只在后端暴露
> `POST /api/json-schema/validate`（§5.1）。

`web/src/api/client.ts` 的 `api` 对象新增方法（契约签名）：

```
validateSchema: (payload: { json_schema: unknown; instance_mode?: 'structured'|'json_text' })
  => Promise<{ valid: true } | { valid: false; errors: SchemaIssue[] }>
```

- 调用 `POST /api/json-schema/validate`（§5.1）；复用既有 `request` 封装与 `ApiError`；
  预检端点返回 200 + `valid:false`，不会进 `ApiError` 分支（只有请求体非法才 4xx）。
- `SchemaIssue` 类型在前端 `types/dataset.ts` 补一份镜像（仅字段，无逻辑）。

## 8. 不变量自查

对照 `AGENTS.md` §2 十五条逐条：

| # | 不变量 | 是否触犯 | 说明 |
| --- | --- | --- | --- |
| 1 | `domain/` 只含不可变数据语义 | 否 | 不改 domain 数据语义；`canonical_json` 是既有工具，复用 |
| 2 | Dataset/Case 拥有期望数据；Evaluator 拥有判断行为 | **触犯边界（M 级）** | 在 evaluator 所有权内新增 size/depth 判断行为；case 层不新增任何 schema 语义。边界内新增，不变量本身不变 |
| 3 | Run 拥有编排，不含 Dataset/Evaluator/Trace/Result 逻辑 | 否 | Run 前校验仍委托 `evaluator/validation.py`，`run/core.py` 只调用 |
| 4 | Trace 适配器在评估器消费前归一化 | 否 | 不涉及 Trace |
| 5 | Result 拥有聚合和 Gate 决策 | 否 | 不涉及 Result/Gate |
| 6 | 外部 Agent/Skill 资产归外部所有 | 否 | 不涉及 |
| 7 | RunSnapshot 存储精确不可变评测内容 | 否 | 不改快照；schema 仍由既有 `content_sha256` 机制纳入快照 |
| 8 | 已发布版本和历史 Run 永不修改 | 否 | 仅新增校验，不改历史数据 |
| 9 | ERROR ≠ Agent FAIL；配置错误在执行前拒绝 | 否（且强化） | size/depth 超限属配置错误，Run 前拒（ValueError），不转 Case Result；与 #9 一致 |
| 10 | 顺序/依赖/严重度/指标权重/Gate 阈值分离 | 否 | limit 是资源保护参数，不与执行顺序/严重度/权重/阈值混用 |
| 11 | Importer 只反序列化格式，不实现评估器算法 | 否 | 不涉及 importer |
| 12 | UI/API 层委托给应用服务，不复制领域规则 | **触犯边界（M 级）** | 新增预检端点 + 应用服务方法，但只委托；规则只在 evaluator。边界内新增，不变量本身不变 |
| 13 | 脚手架不算实现 | 否 | 本计划不含脚手架；implementer 须实现真实校验+测试才算完成 |
| 14 | 状态仅在验收测试通过后变 complete | 否（planner 不改状态） | 本计划不改 progress/capability-mapping 状态值，由 implementer 测试通过后更新 |
| 15 | 公开文档不含私有源文档/客户名/内部需求 ID/凭证/环境密钥 | 否 | 本文档为公开设计，无敏感信息；limit 默认值是公开配置 |

**结论**：触犯 #2、#12 的所有权边界，但在 evaluator/application 所有权**内**新增行为与委托式
契约，不变量**本身不变** → M 级（非契约变更）。需 reviewer 评审。

## 9. 测试策略

### 9.1 后端单元测试（`tests/test_evaluator_validation.py` [MOD]）

新增用例覆盖 `validate_json_schema`：

1. 合法小 schema → 返回空 issue 列表；
2. `size_exceeded`：构造 canonical 序列化 >256KB 的 schema（如巨型 `enum` 数组或超长
   `description`），断言返回 `code='size_exceeded'` 且 `actual > limit`；
3. `size` 边界：恰等于 limit 的 schema 通过（off-by-one 防护）；
4. `depth_exceeded`：构造 >64 层嵌套（如递归 `anyOf`/`properties` 套娃），断言
   `code='depth_exceeded'` 且 `actual > limit`；
5. `depth` 边界：恰 64 层通过；
6. **校验顺序**：构造同时超 size 且超 depth 且 `check_schema` 会抛的 schema，断言命中
   `size_exceeded`（最先触发），证明深/大输入不会到达 `check_schema`（保护生效）；
7. `depth_exceeded` 的 schema **不触发** `RecursionError`（显式栈迭代生效）；
8. 既有用例（unsupported draft / remote ref / invalid check_schema）仍通过（回归）；
9. 环境变量覆盖：`AGENTGATE_JSON_SCHEMA_MAX_DEPTH=10` 时 11 层 schema 被拒（用 monkeypatch
   或 env 设定，测后还原）。

### 9.2 预检 API 集成测试（新建 `tests/test_schema_validation_api.py` [ADD] 或并入既有 server 测试）

1. 合法 schema → 200 + `{valid:true}`；
2. 各失败 code 各一例 → 200 + `{valid:false, errors:[{code,...}]}`，字段齐备；
3. `input_parse_error`：传非法 JSON 文本字符串；
4. `instance_mode` 透传：`json_text` 时校验函数签名收到 `json_text`；
5. 请求体缺 `json_schema` → 422（请求本身非法）；
6. 端点不写校验规则：可通过"调端点=调 service 方法=调 validate_json_schema"的调用链断言
   （mock service 方法，验证端点确实委托而非内联）。

### 9.3 前端测试（可选 e2e）

1. 选 `matches_json_schema` condition → 输入非法 schema → 文本框下方回显后端 message；
2. 预检 API 不可达（mock fetch reject）→ 不阻断保存，草稿仍可存；
3. 前端不出现任何硬编码 limit 数值（grep 前端源码无 `64`/`262144` 等魔法数）。

## 10. Code Change Map

状态标签同 `implementation-plan.md` 约定：`[ADD]` 新建 / `[MOD]` 修改 / `[KEEP]` 复用不变。
前端改动按增量归属另标 `[PR1 已补]`（PR1 已落地）/ `[PR3]`（PR3 才做）；PR2 后端改动用
`[MOD]`/`[ADD]`。

```text
agentgate/
├── src/agentgate/
│   ├── evaluator/
│   │   ├── validation.py                       [MOD] 新增 validate_json_schema 公开函数 +
│   │   │                                             size/depth 闸门 + 可配置 limit 常量；
│   │   │                                             _validate_json_schema_condition 改为复用它
│   │   └── models.py                           [MOD] 新增 SchemaIssue 值对象（§11 决策点 4 定：归 models.py）
│   ├── control_plane/
│   │   └── service.py                          [MOD] EvaluationService 新增 validate_json_schema
│   │                                                方法（委托 evaluator，不复制规则）
│   ├── server/
│   │   └── application.py                      [MOD] 新增预检端点 POST
│   │   │                                             /api/json-schema/validate
│   │   │                                             + ValidateSchemaRequest/响应模型
│   │   └── (routes.py / services.py)          [KEEP] 现状空文件，不动
│   ├── domain/base.py                          [KEEP] 复用 canonical_json，不改
│   ├── case/validation.py                      [KEEP] 不新增 schema 语义（所有权约束 #2）
│   └── case/service.py                         [KEEP] save_case/publish_draft 时序不变
│
├── web/src/                                     〔前端改动归 PR3，PR2 不动〕
│   ├── api/client.ts                           [PR3] api 对象新增 validateSchema 方法
│   ├── types/dataset.ts                        [PR3] 新增 SchemaIssue 镜像类型
│   │                                           （PR1 已加 instance_mode 字段；本项为 SchemaIssue）
│   └── components/dataset/ExpectationEditor.vue [PR1 已补] matches_json_schema 编辑控件已落地
│                                                     〔PR3〕加预检钩子（防抖调 validateSchema、回显、降级）
│
├── tests/
│   ├── test_evaluator_validation.py            [MOD] 新增 size/depth/顺序/边界/环境变量用例
│   └── test_schema_validation_api.py          [ADD] 预检端点集成测试
│
└── docs/
    ├── evaluator/schema-protection-plan.md    [ADD] 本文档
    ├── progress.md                             [MOD] 仅在验收测试通过后由 implementer 更新
    └── capability-mapping.md                  [MOD] 仅在验收通过后由 implementer 更新状态
```

无文件删除。`domain/`、`case/`、`run/`、`result/`、`storage/` 均不改（所有权与既有时序保持）。

## 11. 决策点（已全部确认）

> 以下 5 点已与用户确认定稿，implementer 据此实现，不再征求方向。

1. **limit 最终值**：**已采纳** `max_depth=64`、`max_serialized_size=262144`（256KB）。依据见
   §4。写入 `evaluator/validation.py` 模块默认；环境变量仍可覆盖（§3.2）。
2. **预检 API 路径命名**：**已采纳** `POST /api/json-schema/validate`（动词子路径，非名词资源）。
   依据见 §5.1 + `.tavily/schema-validate-endpoint-naming.md`。原备选 `POST /api/validate-schema`
   与 `POST /api/conditions/matches-json-schema/validate` 均已弃用。
3. **失败响应 HTTP 语义**：**已采纳** HTTP 200 + `{valid:false, errors:[...]}`。schema 不合法是
   业务结果而非请求错误（请求本身合法且被正确处理）；仅当请求体本身不合法（字段缺失/类型错）才
   用 422。server 端点据此实现；前端 `ApiError` 处理无需特殊分支（200 不进错误分支）。
4. **`SchemaIssue` 归属**：**已采纳** 放 `evaluator/models.py`（与 `OperatorOutcome` 等运行时模型
   同处）。`models.py` 在 ledger 中属「runtime-only non-persisted」，SchemaIssue 同属运行时值对象，
   匹配；§6.3、§10 据此。
5. **前端编辑 UI 拆分到独立增量**：**已采纳**——PR1 已先行补齐 `matches_json_schema` 编辑控件
   （含 `setSchema` 两道闸，§7.2）；本增量（PR2）只做后端；PR3 才在已补控件上接预检钩子
   （§7.1/§7.3/§7.4）。

## 12. 验收标准

实现完成的判据（implementer 跑全量质量门后由 primary/reviewer 据此核对）：

- [x] `validate_json_schema` 在 `evaluator/validation.py` 实现，size/depth/draft/ref/check_schema
      六闸门按 §6.2 顺序执行；
- [x] Run 前校验仍以 ValueError 中止（`_validate_json_schema_condition` 复用新函数，行为兼容）；
- [x] 预检端点上线，§5.3 全部错误码可被触发并返回结构化字段，不暴露原始库异常；
- [x] 前端 `ExpectationEditor.vue` 可编辑 `matches_json_schema`，防抖调预检、回显错误、
      不可达时降级不阻断保存；
- [x] 前端源码 grep 不到 limit 数值（64/262144 等），证明 limit 单一源在后端；
- [x] §9 全部测试用例通过；既有 evaluator/case/run 测试回归全绿；
- [x] `ruff check .` / `python -m pytest -q` / `cd web && npm run typecheck` /
      `cd web && npm run build` / `cd web && npm run test:e2e`：增量代码全绿（PR2 `pytest` 200 passed、PR3 `e2e` 6 passed）；全仓 `ruff`/`e2e` 红系 baseline 既有（ruff 0.16.3 I001/UP037、`demo.spec.ts:39` 2-worker flake），非本计划引入；
- [x] 状态记录：`docs/progress.md`、`docs/capability-mapping.md` 为 superseded 历史快照
      （p1-demo / planning-v1），按不变量 #8 不修改；本计划完成由 PR #12（后端）+ PR #13（前端）merge + 测试全绿记录。

## 13. 不做（Out of Scope）

- 不下沉 schema 语义到 case 层（草稿保存/发布仍不拒语义非法 schema）——需另起契约变更。
- 不引入租户级/数据库持久化的 limit 配置——环境变量足够当前阶段。
- 不改 RunSnapshot / content hash 机制——schema 已由既有 `content_sha256` 纳入。
- 不处理 `$ref`/`$dynamicRef` 解析深度（本地 `$defs`/片段引用的解析深度由库负责）；
  远程 $ref 仍由既有闸门禁止。
- 不实现 LLM Judge / Hybrid / 凭证 / 多模态——属 implementation-plan §Deferred Work。
