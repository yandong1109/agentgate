# Dataset Excel 导入导出设计

状态：Draft，作为 Excel 导入导出的目标设计与实现验收依据。

本文只描述 Dataset 的 Excel 能力，不定义 JSON 导入导出、Run、Trace、Target 或
Evaluator 的行为。

## 1. 目标

Excel 能力用于让用户批量维护评估用例，并在不丢失 Case、Turn 和 Expectation
语义的前提下完成以下闭环：

```text
Published DatasetVersion
        │
        ├── 导出 XLSX ──> 用户查看或编辑
        │
        └── 上传 XLSX
                 │
                 ├── 文件与安全校验
                 ├── 行解析、Case/Turn 分组
                 ├── 领域模型校验
                 └── 原子创建新 Dataset + Draft
```

设计目标：

- 导入结果确定、可解释，不静默丢字段或错误合并多轮数据。
- 导入失败不写入任何 Dataset 或 DatasetVersion。
- 所有错误指向原始工作表、真实行号和列名。
- 支持单轮与多轮 Case，支持可选 ID 自动生成。
- 可处理不可信 XLSX，具备文件、ZIP、XML、公式和资源限制。
- 格式可版本化，未来扩展时继续兼容已经导出的文件。

非目标：

- 不在 Excel 内执行公式、宏或外部链接。
- 不支持 `.xls`、`.xlsm`、CSV 或受密码保护的工作簿。
- 不通过 Excel 更新已有 Dataset；每次成功导入都创建新 Dataset 和 Draft。
- 不做部分成功导入。

## 2. 核心决策

| 决策 | 规则 |
|---|---|
| 导出对象 | 只允许导出已发布的 DatasetVersion |
| 导入结果 | 创建新的 Dataset 和一个未发布 Draft |
| 原子性 | Dataset 与 Draft 必须在同一事务内保存 |
| 工作表 | v1 必须包含 `Cases` |
| 必填列 | `case_name`、`input_json` |
| 单轮 Case | `case_id`、`turn_id`、`turn_order` 均可省略 |
| 多轮 Case | 每一轮必须填写相同的 `case_id`；`turn_id` 可省略 |
| Turn 顺序 | 全部不填时按原始行顺序；填写时必须全部填写且为连续的 `1..N` |
| 错误处理 | 收集独立错误，但响应数量有上限；任何错误都阻止保存 |
| 公式 | 所有导入公式拒绝；导出的字符串强制按文本单元格写入 |
| ID | 空 ID 由领域模型生成；非空 ID 原样保留并校验唯一性 |

### 2.1 为什么多轮需要 `case_id`

Excel 是平铺行，无法像 JSON 一样通过嵌套的 `turns` 数组表达归属关系：

| case_id | case_name | turn_order | input_json |
|---|---|---:|---|
| loan-01 | 贷款申请 | 1 | `{"message":"我要申请贷款"}` |
| loan-01 | 贷款申请 | 2 | `{"message":"期限 12 个月"}` |

相同 `case_id` 表示两行属于同一个 Case。缺少 `case_id` 的行只能安全地解释为一个
独立单轮 Case。

用户不需要生成或理解 UUID。`case_id` 在 Excel 中是业务可读的“用例分组编号”，推荐
填写 `loan-001`、`refund-002` 等简短稳定值；同一个多轮 Case 的每一行重复填写同一编号。
模板和 `Instructions` 工作表必须同时提供单轮与多轮示例。

为了避免把用户期望的多轮 Case 静默拆开，导入器必须拒绝以下歧义输入：

- 空 `case_id` 但 `turn_order > 1`。
- 多个空 `case_id` 行具有相同 `case_name`，无法确认是多个单轮还是一个多轮。

错误信息应提示用户为同一个多轮 Case 填写相同 `case_id`。

## 3. XLSX v1 格式

### 3.1 工作表

| 工作表 | 要求 | 用途 |
|---|---|---|
| `Cases` | 必须 | Case 与 Turn 数据，一行代表一个 Turn |
| `Instructions` | 可选 | 字段说明和示例，不参与导入 |
| `Metadata` | 可选于 v1 | 格式版本和来源信息；未来格式中设为必须 |

导入不依赖工作表顺序，只按名称定位 `Cases`。

### 3.2 Cases 列

列可以调整顺序，可选列可以省略。未知列视为错误，防止拼写错误被静默忽略。

| 列 | 必填 | 类型/默认值 | 说明 |
|---|---|---|---|
| `case_id` | 多轮必填 | UUID/字符串；单轮自动生成 | Case 分组键 |
| `case_name` | 是 | 非空字符串 | Case 名称 |
| `case_description` | 否 | `""` | Case 说明 |
| `category` | 否 | `positive` | `positive/negative/boundary` |
| `difficulty` | 否 | `medium` | `easy/medium/hard` |
| `tags_json` | 否 | `[]` | JSON 字符串数组 |
| `initial_state_json` | 否 | `{}` | 初始状态 JSON 对象 |
| `turn_id` | 否 | 自动生成 | 同一 Case 内唯一 |
| `turn_order` | 否 | 按行推断 | 多轮顺序，填写时必须连续 |
| `input_json` | 是 | JSON 对象 | 本轮输入 |
| `expected_skill` | 否 | `null` | 预期 Skill |
| `expectations_json` | 否 | `[]` | Expectation 对象数组 |
| `required_tools_json` | 否 | `[]` | 必须调用的工具名数组 |
| `forbidden_tools_json` | 否 | `[]` | 禁止调用的工具名数组 |
| `policy_rules_json` | 否 | `[]` | 本轮策略规则数组 |
| `turn_notes` | 否 | `""` | Turn 说明 |

JSON 列必须包含 JSON 文本，不能使用 Excel 原生数组、对象或公式。完全空白的行忽略。
显式 JSON `null` 与空白单元格不同：空白使用默认值，`null` 进入领域模型校验。

### 3.3 Case 级字段一致性

同一个 `case_id` 的所有行必须具有相同的以下字段：

- `case_name`
- `case_description`
- `category`
- `difficulty`
- `tags_json`
- `initial_state_json`

不一致时，以后续行作为错误位置，并提示其与该 Case 第一行冲突。导入器不得静默选择
任意一行覆盖其他行。

### 3.4 Turn 顺序

同一 Case 内：

1. 所有 `turn_order` 为空：按原始 Excel 行号生成 `1..N`。
2. 所有 `turn_order` 非空：必须是唯一、连续的 `1..N`，按其排序。
3. 部分为空、部分非空：拒绝导入。
4. `turn_id` 非空时必须在该 Case 内唯一。

Case 的输出顺序按它在 Excel 中首次出现的真实行号确定。Case 行允许交错，但不推荐；
导出器始终连续输出同一个 Case 的所有 Turn。

## 4. 导出设计

### 4.1 服务流程

```text
dataset_id + published version
        │
        ├── 读取 DatasetVersion
        ├── 验证 status=published
        ├── Case 顺序、Turn 顺序展开为行
        ├── JSON 字段使用 canonical compact JSON
        ├── 检查 Excel/XML 可表示性
        └── 生成 XLSX 下载响应
```

导出必须满足：

- 使用 `ensure_ascii=false`，中文不转义为 Unicode 序列。
- JSON 使用稳定紧凑序列化，保证同一版本重复导出语义一致。
- 字符串强制写为文本，避免以 `= + - @` 开头的内容成为公式。
- 单元格超过 32,767 字符或包含非法 XML 字符时，返回结构化导出错误。
- 文件名同时提供 ASCII `filename` 和 RFC 6266 UTF-8 `filename*`。
- Published Version 可使用 `content_sha256` 作为 ETag。

面向人工编辑的导出文件应增加：

- 冻结第一行、自动筛选、合理列宽。
- `category`、`difficulty` 数据验证下拉框。
- `Instructions` 工作表，解释多轮和 JSON 列。
- `Metadata` 工作表，写入 `format=agentgate.dataset.xlsx`、`format_version=1`、
  来源 Dataset ID、版本、内容 hash 和导出时间。

## 5. 导入设计

### 5.1 处理阶段

```text
Multipart upload
    │
    ├─ 1. HTTP 请求大小限制
    ├─ 2. 扩展名、媒体类型、ZIP/OOXML 包检查
    ├─ 3. XML 安全解析和工作簿限制
    ├─ 4. Header 解析
    ├─ 5. Row 解析，并保存真实 source_row
    ├─ 6. 按 case_id 分组、按 turn_order 排序
    ├─ 7. 构建 Case/CaseTurn
    ├─ 8. DatasetVersion 全量领域校验
    └─ 9. 原子保存新 Dataset + Draft
```

解析阶段必须保存来源信息，不得在完成 Case/Turn 重排后重新推算行号：

```text
ParsedCase.source_rows
ParsedTurn.source_row
ParsedField.source_column
```

这些来源信息只用于校验响应，不写入正式 Dataset。

### 5.2 校验层次

| 层次 | 示例 |
|---|---|
| HTTP | 请求过大、缺少文件 |
| 包格式 | 非 ZIP、缺少 OOXML 必需部件、压缩炸弹 |
| Workbook | 缺少 `Cases`、宏、外链、受保护文件 |
| Header | 缺少必填列、重复列、未知列、公式列名 |
| Cell | 必填为空、JSON 错误、公式、错误数据类型 |
| Group | 多轮缺少 Case ID、Case 字段冲突、重复 Turn ID |
| Turn | 顺序缺失、重复或不连续 |
| Domain | Expectation、工具规则、Case/Turn 模型约束 |

只有全部校验通过后才允许持久化。

### 5.3 资源和安全限制

默认限制：

| 限制 | 默认值 |
|---|---:|
| Multipart 请求 | 11 MiB |
| XLSX 文件 | 10 MiB |
| Cases 数据行 | 10,000 |
| 单元格字符 | 32,767 |
| ZIP 总解压大小 | 100 MiB |
| ZIP 单条目解压大小 | 50 MiB |
| ZIP 压缩比 | 200:1 |
| ZIP 条目数 | 2,000 |
| 单次返回错误 | 200 |

安全要求：

- 安装并启用 `defusedxml`，防御 XML entity expansion 和 quadratic blowup。
- `load_workbook(read_only=True, data_only=False, keep_links=False)`。
- 拒绝公式、宏、外部链接、Data Connection、OLE 和嵌入对象。
- 不信任客户端 Content-Type；扩展名、包签名和 OOXML 内容联合校验。
- 原文件不持久化到 Web 可访问路径。
- 生产环境由认证、授权、速率限制和审计日志保护导入接口。
- 超限使用 HTTP `413`，不支持的文件类型使用 `415`，内容校验使用 `422`。

## 6. 错误模型

错误响应必须稳定、可本地化，并保持有界：

```json
{
  "code": "excel_import_validation_failed",
  "total_count": 3,
  "truncated": false,
  "issues": [
    {
      "code": "invalid_json",
      "severity": "error",
      "sheet": "Cases",
      "row": 37,
      "column": "expectations_json",
      "case_id": "loan-01",
      "turn_id": "turn-02",
      "message": "JSON 格式错误"
    }
  ]
}
```

规则：

- `row` 必须是用户原始文件中的真实 Excel 行号。
- API 以 `code` 和参数作为稳定契约，`message` 只用于显示。
- 超过错误上限时继续统计 `total_count`，但不继续保留完整消息。
- Warning 不阻止导入；Error 阻止导入。
- 不向用户返回解析器堆栈、服务器路径或内部异常细节。

## 7. API

### 7.1 当前兼容接口

```text
POST /api/datasets/import/excel
GET  /api/datasets/{dataset_id}/versions/{version}/export/excel
```

导入使用 `multipart/form-data`：

- `file`: XLSX 文件
- `name`: 新 Dataset 名称
- `description`: 可选说明

成功返回 `201`，包含新 Dataset 和 Draft。后续可优化为仅返回 Dataset ID、Draft ID、
Case/Turn 数量和 Warning 摘要，避免大型 Version 重复传输。

### 7.2 目标接口

```text
GET  /api/datasets/excel/template
POST /api/datasets/import/excel/preview
POST /api/datasets/import/excel/{preview_id}/commit
GET  /api/datasets/{dataset_id}/versions/{version}/export/excel
```

Preview 不写数据库，返回：

- 文件 SHA-256 和短期 `preview_id`。
- Case 数、Turn 数、Expectation 数。
- 多轮分组结果、自动生成 ID 数量和默认值摘要。
- Error/Warning。

Commit 必须校验 preview 未过期、文件 hash 未变化，并支持 `Idempotency-Key`，防止双击或
网络重试创建重复 Dataset。

## 8. 持久化与并发

成功导入必须通过一个 Repository 原子操作保存：

```python
repository.save_dataset_with_draft(dataset, draft)
```

要求：

- Dataset 保存失败：不保存 Draft。
- Draft 保存失败：回滚 Dataset。
- 同一个 Preview 重复 Commit：返回第一次提交结果，不重复创建。
- 不修改任何已有 Dataset、Published Version 或 RunSnapshot。

Excel 解析属于 CPU/同步文件工作，异步 HTTP 服务必须在线程池或隔离 Worker 中运行，不能
阻塞主事件循环。

## 9. Web 交互

推荐流程：

```text
下载模板/导出版本
       │
选择 XLSX
       │
上传并校验
       │
预览：Case、Turn、多轮分组、Warnings
       │
确认名称和描述
       │
创建 Draft → 打开新 Dataset
```

Web 必须：

- 选择文件前显示 10 MiB 和 `.xlsx` 限制。
- 上传期间显示进度并防止重复提交。
- 按 Sheet/行/列展示错误，可按行号排序。
- 明确提示“空 `case_id` 行会作为独立单轮 Case”。
- 导入完成后展示 Case/Turn 数量，并直接打开新 Draft。
- 导出失败和导入失败均使用统一错误组件，不产生未处理 Promise。

## 10. 格式演进

v1 保持单个 `Cases` 数据表，优先兼容当前实现。

当 Expectation 或策略数据经常接近单元格字符上限，推出 v2 关系化工作簿：

```text
Metadata
Cases
Turns
Expectations
```

各表通过稳定 ID 关联，避免在一个单元格中维护大型嵌套 JSON。导入器按 Metadata 中的
`format_version` 路由到对应 Decoder：

```text
v1 Decoder ─┐
            ├─> Canonical Cases ─> Domain validation
v2 Decoder ─┘
```

旧 Decoder 不删除；未知的更高版本明确拒绝并提示升级 AgentGate。

## 11. 测试与验收

### 11.1 Codec

- Published Version 导出后再导入，Case/Turn/Expectation 语义一致。
- 中文、换行、Unicode、显式 null 和空白默认值。
- 单轮省略 ID 自动生成。
- 多轮相同 Case ID 正确分组。
- 多轮缺失 Case ID 不静默拆分。
- Case 行交错、Turn 顺序重排后错误仍指向真实行号。
- Header 换序、可选列省略、未知列、重复列和空白行。
- 非法 JSON、重复 ID、Case 字段冲突和非连续 Turn 顺序。

### 11.2 安全与限制

- 文件、Multipart、行数、单元格、ZIP 条目数和解压大小边界。
- 高压缩比、XML entity expansion、宏、外链和嵌入对象。
- 公式位于 Header、必填列、可选列时均拒绝。
- 错误超过上限时返回 `truncated=true`，响应保持有界。

### 11.3 Service/API/Web

- 导入成功创建新 Dataset + Draft。
- 任一步保存失败均完全回滚。
- 只能导出 Published Version。
- 解析工作不阻塞事件循环。
- Preview 不写数据库，Commit 幂等。
- Web 展示真实行列错误并在成功后打开新 Draft。
- 浏览器真实下载的文件可被 Excel、LibreOffice 和 Numbers 打开。

## 12. 当前实现差距

当前分支已经具备基础 Codec、文件/ZIP/XML/主动内容限制、公式拒绝、真实来源行号、
有界结构化错误、专用原子导入、Instructions/Metadata、下载模板、API、Web 入口和自动化
测试。

已完成：

- 多轮缺失 Case ID 的歧义输入不再静默拆分。
- Case 交错和 Turn 重排后的错误使用真实来源行号。
- `defusedxml`、关闭外链、主动内容检查、ZIP 条目数和错误数量上限。
- 使用专用 `save_dataset_with_draft` 原子保存。
- Template、Instructions、Metadata、冻结表头、筛选和列宽。
- HTTP `413/415/422`、UTF-8 文件名、ETag 和有界错误响应。

仍需按优先级完成：

| 优先级 | 差距 |
|---|---|
| P1 | Preview/Commit、重复文件提示和幂等提交 |
| P1 | 为每类 Issue 增加稳定错误 code 和前端本地化文案 |
| P1 | `category`、`difficulty` 下拉数据校验和上传进度 |
| P2 | 大文件临时文件/流式传输优化 |
| P2 | v2 多工作表格式及版本化 Decoder |
