# AgentGate Web 前端重构方案（中文版）

> 版本：v2（对齐 `docs/Agent评测平台-模块划分与协作分工.md` v2 的 15 模块命名，增强代码迁移指引）
>
> 设计依据（权威优先级）：
> - 后端架构：`docs/architecture-review-ledger.md`（refactor-1 13 顶层 + web/）
> - 模块边界：`docs/Agent评测平台-模块划分与协作分工.md` v2（15 模块，去人名）
> - 模块检视：`docs/web-frontend/module-division-review-zh.md`（v1→v2 修订依据）
> - 产品需求：`docs/product-requirements-zh.md`（中文 PRD）
> - 技术规范：`工程架构与编码规范（已脱敏）.md`
> - UI 规范：`2026UI规范 - 已脱敏.pdf`
>
> 协作原则：前后端同一业务域的 owner 相同；后端 Pydantic → 前端 TS 类型 → 前端 api/ → 前端 views/ 四点一线。
> 去人名：`负责人` 列用「域 owner」占位，认领时替换为对应成员账号。
>
> **术语约定（全项目适用）**：
> - **Design Token**（首字母大写）：指设计系统的最小原子变量（颜色/字号/间距/圆角等），源自 W3C Design Tokens 规范。路径用 `src/styles/design-tokens/`。
> - **词元** / **token 数**：指 LLM 上下文分词单位（计费/上下文长度）。本项目文档涉及 LLM 时不单独用裸 "token"。
> - **鉴权 Token**（auth/credential）：指用户登录态或访问凭据（如 JWT、API Key、`Authorization: Bearer xxx`）。代码里用 `utils/auth.ts`、`Authorization` 头，文档里写"鉴权 Token"或"凭据"，不与上述两者混淆。
> - 三者通过首字母大小写 + 上下文区分：Design Token（设计）/ 词元（LLM）/ 鉴权 Token（认证），避免 AI 项目特有的歧义。

---

## 一、现状诊断与差距

### 1.1 技术栈差距

| 维度 | 规范要求（强制） | 现状 | 差距 |
|---|---|---|---|
| 框架 | Vue 3.4 Composition API | Vue ^3.4.0 | 已对齐 |
| UI 库 | Element Plus 2.7.6+ | element-plus ^2.8.0 | 已对齐 |
| 构建 | Vite 4.5.13 | vite ^8.2.1 | 版本跨代（见决策点 D1） |
| 语言 | TS 5.3.3 + vue-tsc | typescript ^5.4.0 | 已对齐 |
| 路由 | vue-router 4.4.0 | 无 | 用 `location.pathname` + `history.pushState` 硬切换（见 [App.vue#L32](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L32)、[L145-L153](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L145-L153)） |
| 状态 | Pinia 2.1.7 | 无 | 状态全在 App.vue 组件内 `ref`（11 个跨页面共享 ref） |
| HTTP | Axios 0.28.1 | 无 | 用原生 `fetch`，无拦截器/统一错误处理（见 [client.ts#L170-L178](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L170-L178)） |
| CSS | SCSS + PostCSS + normalize.css | 无 | 仅 `web/src/style.css` 单文件 |
| Lint | ESLint + Prettier + Husky | 无 | 无强制代码风格 |
| 单测 | @vue/test-utils（建议配 Vitest） | 无 | 仅 Playwright E2E |

### 1.2 现有代码盘点（重构基线）

| 现有文件 | 行数 | 承担职责 | 重构去向 |
|---|---|---|---|
| [main.ts](file:///d:\Develop\myCode_win\agentgate\web\src\main.ts) | 6 | createApp + EP + style.css | 接 Pinia + Router + 全局样式 |
| [App.vue](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue) | ~350 | 评估配置 + 结果报告 + Trace 抽屉 + 重跑/回归弹窗 + 路由 | 拆分到 6 个 views 模块（见 §10.1） |
| [api/client.ts](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts) | 229 | 所有 TS 类型 + fetch 封装 + api 对象 | 类型拆到 types/，fetch 换 Axios，api 拆到 9 个域文件（见 §10.2） |
| [api/datasets.ts](file:///d:\Develop\myCode_win\agentgate\web\src\api\datasets.ts) | - | Dataset 域 API（已存在，未对齐 Axios） | 迁到 api/datasets.ts + types/dataset.ts |
| [types/dataset.ts](file:///d:\Develop\myCode_win\agentgate\web\src\types\dataset.ts) | - | Dataset 领域类型 | 保留，对齐后端 Pydantic |
| [pages/DatasetWorkspace.vue](file:///d:\Develop\myCode_win\agentgate\web\src\pages\DatasetWorkspace.vue) | - | 测评集工作台主视图 | 迁到 views/datasets/index.vue |
| [components/dataset/CaseEditor.vue](file:///d:\Develop\myCode_win\agentgate\web\src\components\dataset\CaseEditor.vue) | - | 用例编辑器 | 迁到 views/datasets/components/ |
| [components/dataset/CaseTable.vue](file:///d:\Develop\myCode_win\agentgate\web\src\components\dataset\CaseTable.vue) | - | 用例表 | 同上 |
| [components/dataset/DatasetList.vue](file:///d:\Develop\myCode_win\agentgate\web\src\components\dataset\DatasetList.vue) | - | 测评集列表 | 同上 |
| [components/dataset/ExpectationEditor.vue](file:///d:\Develop\myCode_win\agentgate\web\src\components\dataset\ExpectationEditor.vue) | - | 期望编辑器 | 同上 |
| [components/dataset/VersionSelector.vue](file:///d:\Develop\myCode_win\agentgate\web\src\components\dataset\VersionSelector.vue) | - | 版本选择器 | 同上 |
| [style.css](file:///d:\Develop\myCode_win\agentgate\web\src\style.css) | - | 全局样式 | 拆到 styles/（Design Token + reset + EP 覆盖） |
> 路径注：Design Token 文件夹用 `src/styles/design-tokens/`（非 `tokens/`），与 LLM 词元概念显式区分。

### 1.3 目录结构差距

现状 `web/src/` 仅 `api/components/pages/router/stores/types` 六个目录，且 `router/`、`stores/` 只有 `.gitkeep`。规范要求的 `layout/styles/utils/hooks/directive/assets` 全部缺失，`router/modules`、`stores/modules` 未落地。

### 1.4 UI 差距

现状是自定义手写 CSS（白底深色字、卡片化布局），无 Design Token、无主题切换、无 8px 栅格、未对齐 UI 规范的 **Emerald Green（翡翠绿 #07ac8e）** 主题与顶导+侧菜单布局。

### 1.5 多人协作冲突点

1. **无模块边界**：所有人改 [App.vue](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue) 与 [client.ts](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts) 必然冲突。
2. **无接口契约层**：API 类型散落在 [client.ts](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts)（229 行集中 15+ 接口），无按业务域拆分。
3. **无共享层 code ownership**：`styles/`、`components/`、`utils/` 缺失，谁改谁冲突。
4. **无 Mock 层**：前端强依赖后端，无法并行开发。
5. **无脚手架约定**：每人按自己习惯建文件，命名/结构不统一。

---

## 二、技术栈对齐方案

### 2.1 依赖增补清单（写入 `web/package.json`）

```jsonc
// dependencies 增补
"vue-router": "^4.4.0",
"pinia": "^2.1.7",
"pinia-plugin-persistedstate": "^3.2.1",
"axios": "^0.28.1",
"normalize.css": "^7.0.0",
"echarts": "^5.4.3",
"@element-plus/icons-vue": "^2.3.1",
"nprogress": "^0.2.0"

// devDependencies 增补
"sass": "^1.77.6",
"postcss": "^8.4.39",
"autoprefixer": "^10.4.19",
"eslint": "^8.57.1",
"eslint-plugin-vue": "^9.20.1",
"@typescript-eslint/parser": "^8.7.0",
"@typescript-eslint/eslint-plugin": "^8.7.0",
"prettier": "^3.3.3",
"husky": "^8.0.3",
"lint-staged": "^13.3.0",
"vitest": "^1.6.0",
"@vue/test-utils": "^2.4.3",
"jsdom": "^24.1.0",
"mockjs": "^1.1.0",
"vite-plugin-mock": "^3.0.0",
"vite-plugin-svg-icons": "^2.0.1",
"plop": "^4.0.1"
```

### 2.2 后端响应契约对齐

工程规范要求后端统一返回 `ResponseBase<T>`（`code`/`message`/`data`，`code="0"` 成功）。当前后端 `src/agentgate/server/routes.py` 未遵循此契约（见决策点 D2）。

`utils/request.ts` 的 Axios 拦截器做适配层：先兼容现有裸 JSON 响应，待后端补齐 `ResponseBase` 后切换。注意 `server/` 是薄路由层，委托 `application/` 对应服务，前端只对接 `server/` 暴露的 REST 路由，不感知 application 内部分层。

---

## 三、目录结构方案（对齐规范 §2.1）

```
web/src/
├── api/                    # 接口定义（按业务域拆分 .ts，前后端契约承载点）
│   ├── datasets.ts         # Case 域
│   ├── evaluators.ts       # Evaluator 域
│   ├── runs.ts             # Run 域
│   ├── targets.ts          # Integrations/Targets 域
│   ├── trace.ts            # Trace 域
│   ├── results.ts          # Result 域
│   ├── analysis.ts         # Analysis 域（静态分析）
│   ├── dashboard.ts        # Application/overview 聚合
│   ├── optimization.ts     # Optimizer 域（P2 预留）
│   ├── experiments.ts      # ab_test/ 域（P2 预留）
│   └── types.ts            # 全局共享响应类型（对齐后端 Pydantic）
├── assets/                 # 静态资源（图片/字体/svg）
├── components/             # 全局通用组件（跨模块复用，共享层）
├── layout/                 # 布局组件（Navbar/Sidebar/AppMain/Breadcrumb）
├── router/
│   ├── index.ts            # 路由实例 + 守卫
│   ├── constant.ts         # 常量路由（登录/404/403）
│   └── modules/            # 按业务域拆分路由表（每域 owner 维护一个文件）
│       ├── dashboard.ts
│       ├── datasets.ts
│       ├── evaluators.ts
│       ├── runs.ts
│       ├── trace.ts
│       ├── results.ts
│       ├── targets.ts
│       ├── analysis.ts
│       ├── optimization.ts
│       └── experiments.ts
├── stores/
│   ├── index.ts            # Pinia 实例 + persistedstate 插件
│   └── modules/            # 跨模块共享 store
│       ├── app.ts          # 布局状态（侧边栏折叠/主题）
│       ├── user.ts         # 用户/权限（预留）
│       └── permission.ts   # 动态路由（预留）
├── styles/                 # 全局 SCSS（Design Token 单点）
│   ├── design-tokens/      # 色彩/字体/间距/圆角/阴影/断点变量（Design Token 定义点）
│   │   ├── _color.scss
│   │   ├── _typography.scss
│   │   ├── _spacing.scss
│   │   ├── _radius.scss
│   │   ├── _elevation.scss
│   │   └── _breakpoint.scss
│   ├── themes/             # light/dark 主题覆盖
│   ├── element/            # Element Plus 主题定制覆盖
│   ├── reset.scss          # normalize + 全局重置
│   └── index.scss          # 统一出口
├── utils/
│   ├── request.ts          # Axios 实例（统一 baseURL/拦截器，禁止 new Axios）
│   ├── auth.ts             # Token 管理（预留）
│   ├── validate.ts         # 校验工具
│   └── format.ts           # 格式化（asPercent/outcomeText 等从 App.vue 抽出）
├── hooks/                  # 全局组合式函数（useXxx.ts）
├── directive/              # 自定义指令（预留）
├── types/                  # 全局共享类型（与后端 Pydantic 对齐）
│   ├── dataset.ts          # Dataset/Case/DatasetVersion/Expectation
│   ├── evaluator.ts        # Evaluator/EvaluatorVersion/RuleConfig/JudgeConfig
│   ├── run.ts              # Run/RunManifest/RunStatus/Attempt
│   ├── target.ts          # TargetDescriptor/TargetRef/Version
│   ├── trace.ts          # Trace/AgentStep/LLMCall/ToolCall
│   ├── result.ts          # Result/CheckResult/Gate/Metric/Evidence/Outcome
│   └── dashboard.ts       # Overview 聚合
└── views/                  # 业务页面（按模块组织，每域 owner 一个目录）
    ├── dashboard/          # 总览（Application/overview.py 域，P2 占位先）
    ├── targets/            # Agent/Skill 版本管理（Integrations/Targets 域）
    ├── datasets/           # 测评集管理（Case 域）
    ├── evaluators/         # 评估器管理（Evaluator 域）
    ├── runs/               # 运行调度（Run 域）
    ├── trace/              # Trace drill-down 组件库（Trace 域）
    ├── results/            # 结果中心（Result 域）
    ├── analysis/           # 静态分析（Analysis 域，可并入 datasets/ 子页）
    ├── optimization/       # 调优中心（Optimizer 域，P2 预留占位）
    ├── experiments/        # A/B Test（ab_test/ 域，P2 预留占位）
    └── system/             # 系统设置（共享）
```

每个 `views/<module>/` 内部约定：

```
views/<module>/
├── index.vue          # 模块入口（列表/主视图）
├── components/         # 模块私有组件（XxxDialog/XxxDrawer/XxxTable 命名）
├── hooks/             # 模块级组合式函数（可选）
├── types/             # 模块级类型（可选）
└── utils/             # 模块级工具（可选）
```

---

## 四、模块划分方案（对齐 v2 分工文档 15 模块）

### 4.1 前后端同域映射表（权威·对齐 v2 分工文档 §4）

| 后端模块（ledger 顶层） | 前端 views 模块 | API 文件 | 共享契约（types/） | 负责人 |
|---|---|---|---|---|
| `case/` + `application/dataset_management.py` | `views/datasets/` | `api/datasets.ts` | `dataset.ts` | 待定（Case 域 owner） |
| `evaluator/` + `application/evaluator_management.py` | `views/evaluators/` | `api/evaluators.ts` | `evaluator.ts` | 待定（Evaluator 域 owner） |
| `run/` + `application/run_management.py` | `views/runs/` | `api/runs.ts` | `run.ts` | 待定（Run 域 owner） |
| `integrations/targets/` + `application/target_catalog.py` | `views/targets/` | `api/targets.ts` | `target.ts` | 待定（Integrations/Targets 域 owner） · **归评测中心组**（评测对象=外部输入，非资产） |
| `trace/` + `application/result_reader.py`(Trace 部分) | `views/trace/` | `api/trace.ts` | `trace.ts` | 待定（Trace 域 owner） · **不暴露顶级路由**，作为 results 下钻抽屉 |
| `result/` + `application/result_reader.py` | `views/results/` | `api/results.ts` | `result.ts` | 待定（Result 域 owner） · 含 Trace 下钻 |
| `analysis/` + `application/dataset_generation.py`（未来） | `views/analysis/`（可并入 datasets/ 子页） | `api/analysis.ts` | `AnalysisFinding` | **本期前端移除**（伪需求，详见 §5.2.1） |
| `optimizer/` | `views/optimization/`（ComingSoon 占位先） | `api/optimization.ts` | Cluster/RootCause/Suggestion | 待定 P2（Optimizer 域 owner） |
| `application/overview.py` | `views/dashboard/`（ComingSoon 占位先） | `api/dashboard.ts` | `dashboard.ts` | 待定（Dashboard owner） |
| `ab_test/`（预留） | `views/experiments/`（ComingSoon 占位先） | `api/experiments.ts` | Experiment/PairedStats | 待定 P2+（ab_test 域 owner） |

### 4.2 前端 ownership 三组

#### A · 个人 owning 模块（`views/<module>/`，低冲突区）

| 前端模块 | 对应后端域 | 主要页面 | 当前实现状态 |
|---|---|---|---|
| `datasets/` | Case 域 | 测评集列表 · 用例编辑器 · 版本管理 · 自动生成 · 导入导出 | 部分实现（[DatasetWorkspace.vue](file:///d:\Develop\myCode_win\agentgate\web\src\pages\DatasetWorkspace.vue) + 5 组件） |
| `results/` | Result 域 | 结果报告 · 指标 · Badcase · 版本对比 · 回归集 | 部分实现（混在 [App.vue](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue)） |
| `evaluators/` | Evaluator 域 | 评估器列表 · 创建（规则/LLM/复合）· 详情 | 未实现（仅选择器在 [App.vue#L216](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L216)） |
| `runs/` | Run 域 | 运行配置 · 调度 · 历史 · 运行详情 | 部分实现（评估配置在 [App.vue#L187-L225](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L187-L225)） |
| `targets/` | Integrations/Targets 域 | 评测对象管理（外部 Agent/Skill 接入 + 本地 demo）· 归评测中心组 | 未实现（仅版本选择器在 [App.vue#L193-L198](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L193-L198)） |
| `trace/` | Trace 域 | Trace drill-down 组件库 · 标准化展示 · 导入（**不占顶级菜单**，results 下钻抽屉） | 部分实现（Trace 抽屉在 App.vue） |
| `analysis/` | Analysis 域 | 静态分析结果（**本期前端移除**，伪需求，详见 §5.2.1） | 未实现 |

#### B · 共享基础设施（`src/` 全局层，高冲突区，1 人专职负责）

| 前端目录 | 主要职责 | 对应后端 |
|---|---|---|
| `layout/` `styles/` `components/` | 顶导+侧菜单布局 · Design Token · 主题 · 全局通用组件 | Web Frontend（前端工程） |
| `router/` `stores/` `utils/` `hooks/` | 路由骨架 · Pinia · Axios 实例 · 全局组合式函数 | Server/Application 配套 |
| `api/types/` `mock/` | 接口契约层 · TS 类型对齐 Pydantic · Mock 数据 | 各域 owner 提 PR |

#### C · P2 预留占位模块

| 前端模块 | 主要页面 | 对应后端 |
|---|---|---|
| `dashboard/` | 总览：Agent/Skill 数 · 任务数 · 通过率趋势 · 失败类型 | `application/overview.py` |
| `optimization/` | 调优中心：聚类 · 混淆矩阵 · 根因 · 优化建议 | `optimizer/` |
| `experiments/` | A/B Test：版本对比分析 · 迭代选型决策 | `ab_test/`（预留） |

### 4.3 共享层 code ownership（关键决策）

组 B 是冲突高发区，必须指定 **1 人专职负责**（角色名"前端基础设施 owner"）。其独占写权限：
- `src/layout/`、`src/styles/`、`src/components/`、`src/router/index.ts`、`src/utils/request.ts`、`src/stores/modules/app.ts`
- 其他人对共享层**只读使用**，需求变更走 PR 提交，由基础设施 owner 审核合并

### 4.4 接口契约先行

`src/api/<domain>.ts` 作为前后端契约承载点，**先定义 TS 类型（对齐后端 Pydantic 模型），再写页面**。各域 owner 维护自己的 api 文件，类型放 `src/types/<domain>.ts` 全局共享或 `views/<module>/types/` 模块级。

### 4.5 消费关系（非 owning）

- `results/`（Result 域）消费 `trace/`（Trace 域）的 Trace 查看器组件与 `evaluators/`（Evaluator 域）的评估器元数据 → 通过组件 props 与 store 读取，**不跨模块改文件**；Trace 作为 results 下钻抽屉，不暴露顶级路由
- `runs/`（Run 域，评测中心组）消费 `targets/`（Integrations/Targets 域，同组）的 Agent 选择器组件——评测对象作为评测闭环起点
- `dashboard/` 消费所有模块的聚合 API
- ~~`analysis/` 产出供 `datasets/` 自动生成消费~~ → **本期移除**（伪需求，详见 §5.2.1）；若未来做，产出"测试点"归 datasets，产出"可优化点"归 optimization

### 4.6 冲突消解原理

- 组 A：每域 owner own 独立目录，互不修改对方文件 → 零冲突
- 组 B：共享层由 1 人专职负责，其他人提 PR → 单点合并
- 组 C：仅占位页，任何人都可先建骨架

---

## 五、UI 重设计方案（对齐 2026UI 规范）

### 5.1 Design Token 体系（写入 `src/styles/design-tokens/`）

> **术语澄清**：本项目的 "Design Token" 指设计系统的最小原子变量（颜色/字号/间距/圆角等，源自 W3C Design Tokens 规范），与 LLM 词元（LLM 上下文分词单位，本项目称"词元"或"token 数"）是两个不同概念。本文档统一用 "Design Token"（首字母大写）指代设计变量，用"词元"指代 LLM 分词单元，避免歧义。

| Token 类 | 落地值（取自 UI 规范） |
|---|---|
| 主色 Primary | `#07ac8e`（Emerald Green） |
| Primary Hover | `#02b38a` · Active `#00957a` · Lighter `#d5f1ec` |
| 语义色 | Success `#02b38a` · Warning `#fba45` · Error `#ef4444` · Info `#3b82f6` |
| 中性色 | Gray-900 `#111827` → Gray-50 `#f9fafb`（8 阶） |
| 字族 | 中文 PingFang/雅黑 · 英文 Inter · 等宽 JetBrains Mono |
| 字号阶梯 | H1 32 / H2 24 / H3 20 / H4 16 / Body 14 / Small 12 |
| 间距 | 8px 栅格：xs4/sm8/md12/lg16/xl20/2xl24/3xl32/4xl48/5xl64 |
| 圆角 | `--radius` 8px · `--radius-card` 12px · `--radius-full` 999px |
| 断点 | sm 640 / md 768 / lg 1024 / xl 1280 |
| 动效 | 150-500ms · ease-in-out · 悬停变深不变浅 |

### 5.2 布局方案（顶导 + 侧菜单）

按 UI 规范 E.6 落地 `src/layout/`：
- 顶部导航：高 64px，含 Logo / 全局搜索（预留）/ 用户菜单
- 侧边菜单：宽 220px（可折叠至 64px），按用户任务工作流分组（UCD，非按后端模块平铺）
- 内容区：内边距 24px，最大宽度 1600px 居中
- 响应式：< 768px 汉堡菜单 + 单列

#### 5.2.1 菜单信息架构（UCD · 4 组 + 总览）

菜单层按用户任务工作流分组，文件层仍按 owner 域分（解耦）。下钻证据（Trace/静态分析）不占顶级菜单项，归入宿主任务内的抽屉或 Tab。

| 菜单组 | 子项 | 性质 | 路由 |
|---|---|---|---|
| 总览 | 总览 | 全局看板 | `/dashboard` |
| 资产管理 | 测评集 | 平台资产·Case/版本/导入导出 | `/datasets` |
| | 评估器 | 平台资产·内置只读 + 自定义预留 | `/evaluators` |
| 评测中心 | 评测对象 | 外部 Agent/Skill 接入 + 本地 demo（闭环起点） | `/targets` |
| | 发起评测 | 选 target+dataset+evaluator 启动 | `/runs` |
| | 运行记录 | 历史 Run 列表 | `/runs/history` |
| | 结果报告 | 指标 + Case + Trace 下钻抽屉（闭环终点）★ | `/results/:id` |
| 调优 | 调优中心 | Badcase 根因/建议 | `/optimization` |
| 实验对比 | A/B 实验 | 未来 | `/experiments` |

**下钻证据归属**：
- Trace = 结果报告的下钻（`views/trace/components/TraceDrawer.vue` 在 results 页内调用，**不暴露 `/trace` 顶级路由**）
- 静态分析 = **本期移除**（伪需求）；若未来做，产出"测试点"归入测评集管理，产出"可优化点"归入调优中心
- 评测对象 = 评测的**输入**（外部拥有，[target_catalog.py](file:///d:\Develop\myCode_win\agentgate\src\agentgate\control_plane\service.py) "externally owned"），非平台资产；归入评测中心组作为闭环起点

**Run 译法**：领域对象（类名/枚举/文件名）保留 `Run`，文档译"评测运行"；菜单不用"运行"单项，拆为"发起评测"+"运行记录"，消除"运行"歧义

#### 5.2.2 评估器管理页设计（资产权限分层）

评估器是平台资产，分内置（系统预置，只读）与自定义（用户创建，可读写）两类，统一在 `/evaluators` 页管理。对齐 GitHub 内置 Actions、Notion 内置模板的权限分层模式。

| 列 | 内容 | 说明 |
|---|---|---|
| id | `skill-routing` 等 | 评估器唯一标识 |
| name | 技能路由 等 | 中文名 |
| kind | rule / llm_judge / hybrid | 当前全是 rule，未来扩展 |
| dimension | ROUTING / TOOL_USE / STATE / ANSWER / SAFETY | 评测维度 |
| metric | `skill_routing_accuracy` 等 | 指标名 |
| severity | BLOCKING / STANDARD | 是否阻断发布 |
| **source** | **内置** badge（灰）/ **自定义** badge（品牌色） | 来源标记 |
| 操作 | 内置→「查看」；自定义→「编辑」「删除」 | 权限分层 |
| 顶部 | 「新建评估器」按钮 | 当前禁用 + tooltip"自定义评估器 P2 支持"，预留入口 |

**后端契约建议**（非阻塞）：`service.evaluators()` 返回里补 `source: "builtin"|"user"` 字段。当前后端 7 个内置评估器全无此字段（见 [evaluator/__init__.py#L10-L43](file:///d:\Develop\myCode_win\agentgate\src\agentgate\evaluator\__init__.py#L10-L43)），前端默认 `source="builtin"`，等后端补字段再切换。

### 5.3 Element Plus 主题定制

用 SCSS 变量覆盖 Element Plus 主题（`src/styles/element/index.scss`）：

```scss
@forward 'element-plus/theme-chalk/src/common/var.scss' with (
  $colors: ('primary': ('base': #07ac8e)),
  $border-radius: ('base': 8px)
);
```

### 5.4 暗黑模式（规范未覆盖，方案补全）

建立 `src/styles/themes/dark.scss`，通过 `:root[data-theme="dark"]` 覆盖 Design Token，配合 `stores/modules/app.ts` 持久化用户偏好。Element Plus 暗黑模式用官方 `dark/css-vars.css`。

### 5.5 页面级视觉重构要点

当前 [App.vue](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue) 的"评估配置 + 结果报告"主流程拆分（详见 §10.1 迁移清单）：
- `views/runs/components/RunConfigPanel.vue`（评估配置卡 A/D/E 三卡）
- `views/runs/components/LaunchBar.vue`
- `views/results/index.vue`（结果报告主视图）
- `views/results/components/MetricGrid.vue`、`CheckResultList.vue`、`RecentRunsTable.vue`、`RerunComparison.vue`
- `views/trace/components/TraceDrawer.vue`、`TraceTimeline.vue`、`TurnInspector.vue`
- `views/results/components/RerunDialog.vue`、`RegressionDialog.vue`

[DatasetWorkspace.vue](file:///d:\Develop\myCode_win\agentgate\web\src\pages\DatasetWorkspace.vue) + 5 个 dataset 组件整体迁到 `views/datasets/`，组件迁到 `views/datasets/components/`。

### 5.6 结果报告页信息架构（已在 web-new 落地）

页面级布局自上而下（`views/results/index.vue`）：

```
RunToolbar（← 切换 Run → + 当前 Run 摘要 + 运行记录按钮）
GateBanner（门禁决策大色块横幅：通过率/通过/失败/门槛）
MetricGrid（指标卡：维度色彩条 + 失败标红 + 大字号 score）
CheckResultList（Tab 分类 + Case 折叠列表）全宽
```

**交互原则**：

| 原则 | 实现 |
|---|---|
| 切 Run 不离开结果页 | RunToolbar ←/→ + RunHistoryDrawer 抽屉（复用 RecentRunsTable），移除结果页右侧常驻 Run 列表 |
| Run 列表浏览归 `/runs/history` 独立页 | 消除"结果页有最新运行、运行记录页也有"的重复 |
| 页面不出现设计说明文案 | 标题即"结果报告"，Run 上下文由 RunToolbar 数据承载 |

#### 5.6.1 Case 列表（浏览模式）

| 项 | 约定 |
|---|---|
| 默认 Tab | **全部**（先看所有用例状态总览） |
| 默认折叠状态 | **全部折叠**（状态总览 → 需要细看才点开某用例，信息按需释放） |
| Tab 分类 | 全部 / 失败 / 通过 / 不适用（按 Case 级聚合结果过滤） |
| Case 行 | 用例名 + 状态 Tag + 操作（查看 Trace / 加入回归集 / 重新运行） |

#### 5.6.2 用例详情（展开后的信息层级）

展开 Case 后两级渐进披露（CaseDetailPanel + 检查结果）：

```
Case 标题  [失败]  查看Trace | 加入回归集 | 重新运行
  └ ▸ 用例详情（输入侧：用户给了什么）
      ├ 元信息：正向/反向/边界 · 难度 · tags · 回归来源
      ├ 初始状态 initial_state
      └ ▸ 每轮输入 input（标题行预览）+ 轮次备注
  └ 评估器结果 + 期望/实际对比（判定侧：比什么、怎么比、比出什么）
```

**输入侧与判定侧分离**：期望技能/必需工具/禁用工具/期望条件不在用例详情中重复展示——它们是判定侧的期望值，归对比面板。

#### 5.6.3 期望/实际对比面板（ExpectedActual，两栏布局）

阅读顺序 = **"期望 xxx 项符合 xxx 判定方式和条件，值是什么，实际是什么"**：

```
┌─ 期望 ──[数值容差 ±0.1]──┐  ┌─ 实际 ──────────┐
│ 0.9                      │  │ 0.85（红框）     │
└──────────────────────────┘  └──────────────────┘
```

- **判定方式归期望**：算子徽标（+附带条件如 ±ε）放期望框头部，不放两框中间
- **期望纯化**：condition dump（`{"kind":"equals","expected":…}`）拆解——kind→判定方式徽标、值→期望框体、epsilon/instance_mode→附带条件小字
- **实际框按结果着色**：失败红框红头 / 通过绿框；值差异行黄底高亮；一致显示"一致"徽标
- **边界视觉稳定**：空值 `min-height: 30px`、超长折叠渐隐（6 行阈值）+ 展开按钮、`overflow-wrap: anywhere`、窄屏两栏退化上下堆叠

**判定方式名称与创建用例时一致**（数据源 `CheckResult.methods.operator`，见 [ExpectationEditor.vue](file:///d:\Develop\myCode_win\agentgate\web\src\components\dataset\ExpectationEditor.vue) 选项文案）：

| 算子 | 显示名 | 附带条件 |
|---|---|---|
| equals | 等于 | — |
| within_tolerance | 数值容差 | 容差 ±ε |
| within_range | 数值范围 | — |
| matches_pattern | 正则匹配 | — |
| one_of | 属于集合 | — |
| must_be_missing | 字段不存在 | — |
| matches_json_schema | JSON Schema 校验 | 直接校验值 / 解析 JSON 文本后校验 |
| contains_all | 必须调用 | —（必需工具 ⊆ 实际调用） |
| contains_none | 禁止调用 | —（禁用工具 ∉ 实际调用） |
| 特判 | 策略合规 check 本身即规则名，键值对等于判定 | — |

**期望纯值 vs 判定附带条件归类表**：

| 来源 | 期望纯值 | 判定方式 | 附带条件 |
|---|---|---|---|
| skill-routing | `expected_skill` | 等于 | — |
| required-tool | tool 名 | 必须调用 | — |
| forbidden-tool | 解包 `{"absent_tool": x}` → `x` | 禁止调用 | — |
| policy | 键值对（路径: 值） | 等于 | — |
| equals | `expected` | 等于 | — |
| within_tolerance | `expected` | 数值容差 | 容差 ±ε |
| within_range | `min ~ max` | 数值范围 | — |
| matches_pattern | `/pattern/` | 正则匹配 | — |
| one_of | `allowed` 列表 | 属于集合 | — |
| must_be_missing | 无（占位"该字段应不存在"） | 字段不存在 | — |
| matches_json_schema | `json_schema` 本体 | JSON Schema 校验 | 直接校验值 / 解析 JSON 文本后校验 |

#### 5.6.4 组件清单（`views/results/components/`）

| 组件 | 职责 |
|---|---|
| RunToolbar.vue | Run 切换（←/→/抽屉）+ 当前 Run 摘要 |
| RunHistoryDrawer.vue | 右侧抽屉选 Run（复用 RecentRunsTable） |
| GateBanner.vue | 门禁决策横幅（大色块 + 关键数字） |
| MetricGrid.vue | 指标卡网格（维度色彩条/失败标红/大字号） |
| CheckResultList.vue | Tab 分类 + Case 折叠列表（默认全折叠） |
| CaseDetailPanel.vue | 用例详情（输入侧，两级折叠） |
| ExpectedActual.vue | 期望/实际两栏对比（判定方式归期望框头） |
| TraceDrawer.vue（views/trace/） | Trace 下钻抽屉 |
| RerunDialog / RegressionDialog / RerunComparison | 重跑/回归/对比 |

**后端契约增强建议**：CheckResult 已含 `methods` 字段（FastAPI 全字段序列化），前端 `types/result.ts` 已加 `MethodRef`。后续可在 check 结果中补 `expectation_id`，对比面板即可显示该 check 关联的具体期望条件。

---

## 六、协作与工程化策略

### 6.1 强制工程化基线

| 项 | 约定 |
|---|---|
| 代码风格 | ESLint + Prettier + Husky + lint-staged，pre-commit 强制 |
| 组件命名 | PascalCase（如 `VersionManageDrawer.vue`） |
| 组件写法 | `<script setup lang="ts">` + Composition API |
| 请求 | 统一走 `@/utils/request`，**禁止 new Axios**，**禁止 fetch** |
| 代码编辑器 | 用 `:model-value` + `@update:modelValue`，**禁止 v-model** |
| TS | 严格模式，接口参数/返回值显式标注类型 |
| 状态 | 跨模块用 Pinia，组件内用 ref/reactive |

### 6.2 Mock 先行（解耦前后端）

`vite-plugin-mock` + `mockjs`，在 `mock/` 下按业务域建文件。后端未就绪时，前端用 Mock 数据独立开发，切换通过环境变量 `VITE_USE_MOCK` 控制。这让团队前端不必等后端 API。

### 6.3 脚手架（plop）

用 `plop` 生成模块骨架：`plop view` 一键生成 `views/<name>/{index.vue,components/,hooks/,types/,utils/}` + `api/<name>.ts` + `router/modules/<name>.ts` + `mock/<name>.ts`，统一约定，杜绝结构不一致。

### 6.4 分支与 PR 策略

- 分支命名：`feature/<module>-<feature>`（如 `feature-datasets-case-editor`）
- 主分支 `main` 受保护，强制 PR + CI（typecheck + lint + test）通过
- 共享层 PR 由基础设施 owner 审核；模块 PR 由对应域 owner 审核
- CODEOWNERS 文件（仓库根）按域 owner 锁定所有权路径：
  ```
  /web/src/layout/               @frontend-infra-owner
  /web/src/styles/               @frontend-infra-owner
  /web/src/components/           @frontend-infra-owner
  /web/src/views/datasets/       @case-domain-owner
  /web/src/views/results/        @result-domain-owner
  /web/src/views/evaluators/     @evaluator-domain-owner
  /web/src/views/runs/           @run-domain-owner
  /web/src/views/targets/        @integrations-targets-domain-owner
  /web/src/views/trace/          @trace-domain-owner
  /web/src/views/analysis/       @analysis-domain-owner
  ```
  > 实际认领时把上述占位符替换为团队对应成员的 GitHub/GitLab 账号。

### 6.5 预留占位页（让人看到产品样子）

未实现模块用统一 `<ComingSoon />` 组件落地，包含：模块图标、标题、一句话描述、预计阶段（P2）、空状态插画。让人能点进 Dashboard / 调优 / A-B 菜单看到"产品未来样子"，而非 404。

---

## 七、迁移路线（从现状到目标）

### 7.1 阶段表

| 阶段 | 目标 | 负责 | 产出 | 验收标准 |
|---|---|---|---|---|
| S0 基础设施 | 装依赖、建目录骨架、配 ESLint/Prettier/Husky、Axios 实例、Pinia、Router 骨架、Mock 插件 | 基础设施 owner | 可跑的空壳 + Design Token + 布局 | `pnpm dev` 启动无报错；`pnpm lint` 通过；侧边菜单可点击跳转占位页 |
| S1 共享层 | `layout/`（顶导+侧菜单）、`styles/`（Design Token+主题+EP 覆盖）、`components/`（ComingSoon/PageContainer/EmptyState） | 基础设施 owner | 新 UI 壳 + 路由表可点所有菜单 | 顶导显示 Logo + 用户菜单；侧菜单含 10 个业务域分组；主题色为 #07ac8e；暗黑模式可切换 |
| S2 并行重构 | 各域 owner 在自己 `views/<module>/` 内迁移现有功能（按 §10 迁移清单逐块 PR） | 各域 owner | 拆分 App.vue，主流程跑通 | 评估配置→启动→结果报告→Trace→重跑→回归 全流程在新路由下可用；旧 App.vue 删除 |
| S3 预留占位 | dashboard/optimization/experiments/analysis 落地 ComingSoon 页 + 路由占位 | 共享 | 全菜单可达，产品样子完整 | 点任意菜单都有内容，无 404 |
| S4 联调测试 | 接后端真实 API、切 Mock、补 Vitest 单测、Playwright E2E 回归 | 全员 | 交付可发布 | 核心 API 有单测；E2E 覆盖主流程；`VITE_USE_MOCK=true/false` 切换无报错 |

### 7.2 S2 重构顺序（依赖关系，避免破坏现有功能）

```
1. 先迁 types/（从 client.ts 抽类型，零行为变化）
   ↓
2. 再迁 utils/request.ts + utils/format.ts（fetch→Axios，asPercent 等抽出）
   ↓
3. 再迁 api/<domain>.ts（按域拆 client.ts 的 api 对象）
   ↓
4. 再迁 stores/（把 App.vue 的 11 个 ref 按域归入 Pinia）
   ↓
5. 再迁 views/datasets/（已有 DatasetWorkspace + 5 组件，最独立，先验证迁移模式）
   ↓
6. 再迁 views/runs/ + views/results/（评估配置 + 结果报告，主流程核心）
   ↓
7. 再迁 views/trace/ + views/targets/ + views/evaluators/（被主流程消费的组件库）
   ↓
8. 最后删 App.vue + pages/DatasetWorkspace.vue，router 接管路由
```

**关键约束**：每块独立 PR，避免一次性大爆炸重构。每步迁完跑一次 Playwright E2E 回归，确保功能不退化。

---

## 八、决策点与风险

| ID | 决策 | 选项 | 建议 |
|---|---|---|---|
| D1 | Vite 版本 | 规范要求 4.5.13 / 现状 8.2.1 | **保持 8.2.1**：规范版本为示例，8.x 兼容性更好且已是主流；如客户审计要求严格对齐规范则降级 |
| D2 | 后端 ResponseBase 契约 | 现状裸 JSON / 规范 ResponseBase | Axios 拦截器做适配层先兼容，推动后端补齐 `ResponseBase<T>` |
| D3 | HTTP 库 | fetch / Axios | **Axios**：规范强制，且需拦截器/超时/重试 |
| D4 | 单测框架 | Vitest / Jest | **Vitest**：与 Vite 原生集成，零配置 |
| D5 | i18n | 引入 / 暂不 | **暂不**：规范未要求，当前中文单语；预留 `vue-i18n` 接入点 |
| D6 | EP 主题定制 | CSS 变量 / SCSS 覆盖 | **SCSS 覆盖**：规范明确 sass 方案，且 EP 官方支持 |
| D7 | 共享层 owner | 从团队中指定 1 人 | **关键**：未指定则冲突无法消除 |

---

## 九、下一步

落地前需确认两点：

1. **共享层 owner 人选**（D7）——这是消除多人冲突的关键，需从团队中明确指定 1 人专职负责 `layout/styles/components/router/utils`。
2. **Vite 版本策略**（D1）——是否允许保持 8.x，还是必须严格降级到规范示例的 4.5.13。

确认后即可启动 S0：生成依赖增补、ESLint/Prettier/Husky 配置、目录骨架、Axios 实例、Pinia/Router 接入、Design Token 与 Element Plus 主题覆盖、布局组件、plop 模板。

---

## 十、现有代码迁移清单（指导 S2 重构）

### 10.1 App.vue 拆分映射（按功能块 → 目标组件）

| App.vue 功能块 | 行号区间 | 迁移目标 | 说明 |
|---|---|---|---|
| 顶导 header + nav 按钮 | [L173-L184](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L173-L184) | `layout/components/Navbar.vue` | nav 按钮换 `<router-link>` |
| `page` 路由状态 + `navigate()` + `onPopState` | [L32](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L32)、[L145-L153](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L145-L153) | 删除，由 Vue Router 接管 | `<router-view>` 替代 `v-if="page"` |
| `overview/versions/datasets/evaluators/runs` ref + `refresh()` | [L7-L11](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L7-L11)、[L60-L71](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L60-L71) | `stores/modules/dashboard.ts` + `api/dashboard.ts` | 5 个 ref 归入 dashboard store |
| `selectedVersion/selectedDataset/selectedEvaluators` ref | [L12-L14](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L12-L14) | `stores/modules/run.ts` | 评估配置状态归入 run store |
| `report/trace/comparison` ref + `openRun/openTrace` | [L15-L17](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L15-L17)、[L88-L93](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L88-L93) | `stores/modules/result.ts` + `api/results.ts` + `api/trace.ts` | 报告/Trace/对比分别归域 |
| `rerunOpen/rerunCaseId/rerunVersion` ref + `openRerun/submitRerun` | [L18-L22](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L18-L22)、[L94-L111](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L94-L111) | `views/results/components/RerunDialog.vue` + `api/runs.ts` | 弹窗组件化，状态组件内 ref |
| `regression*` ref + `openRegression/submitRegression` | [L23-L31](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L23-L31)、[L112-L144](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L112-L144) | `views/results/components/RegressionDialog.vue` + `api/datasets.ts` | 同上 |
| `groupedVersions/selectedAgent/selectedDatasetInfo/regressionDatasets` computed | [L42-L53](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L42-L53) | 拆到对应 views 内的 computed | 按消费方拆分 |
| `caseNames/failed/caseResults` computed | [L34-L41](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L34-L41) | `views/results/index.vue` 内 computed | 结果报告局部状态 |
| `launch()` | [L73-L86](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L73-L86) | `views/runs/components/LaunchBar.vue` + `api/runs.ts` | 启动按钮组件化 |
| `agentLabel()` | [L55-L58](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L55-L58) | `utils/format.ts` | 工具函数 |
| `asPercent/outcomeText/outcomeType/comparisonText/comparisonType` | [L160-L164](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L160-L164) | `utils/format.ts` | 全局工具函数 |
| 评估配置区 template（config-region + A/D/E 三卡） | [L186-L225](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L186-L225) | `views/runs/components/RunConfigPanel.vue` | A 卡→targets 域选择器；D 卡→datasets 域选择器；E 卡→evaluators 域选择器 |
| 结果报告区 template（result-report） | [L226-L280](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L226-L280) | `views/results/index.vue` + `MetricGrid.vue` + `CheckResultList.vue` + `RecentRunsTable.vue` | 拆 4 个子组件 |
| Trace 抽屉 template | [L281-L310](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L281-L310) | `views/trace/components/TraceDrawer.vue` + `TraceTimeline.vue` + `TurnInspector.vue` | 抽屉 + 时间线 + 检视器三件套 |
| Rerun 弹窗 template | [L311-L330](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L311-L330) | `views/results/components/RerunDialog.vue` | 弹窗组件化 |
| Regression 弹窗 template | [L331-L350](file:///d:\Develop\myCode_win\agentgate\web\src\App.vue#L331-L350) | `views/results/components/RegressionDialog.vue` | 弹窗组件化 |

### 10.2 client.ts 拆分映射（类型 → types/，API → api/）

| client.ts 内容 | 行号 | 迁移目标 |
|---|---|---|
| `Version` interface | [L6-L13](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L6-L13) | `types/target.ts`（Version = TargetDescriptor + TargetRef） |
| `DatasetOption` / `DatasetSummary` / `DatasetVersion` / `EvaluationCase` / `DatasetRecord` / `JsonObject` / `SchemaValidationResult` | [L1-L4](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L1-L4)、[L14](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L14) | `types/dataset.ts`（已存在，补齐） |
| `EvaluatorOption` | [L15-L25](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L15-L25) | `types/evaluator.ts` |
| `Run` interface | [L26-L42](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L26-L42) | `types/run.ts` |
| `Evidence` / `Outcome` / `CheckResult` / `Result` / `Gate` / `Metric` / `Report` | [L43-L98](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L43-L98) | `types/result.ts` |
| `ComparisonStatus` / `RerunComparison` | [L99-L117](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L99-L117) | `types/result.ts`（comparison 子集） |
| `TraceTurn` / `Trace` | [L118-L136](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L118-L136) | `types/trace.ts` |
| `Overview` | [L137-L142](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L137-L142) | `types/dashboard.ts` |
| `AddRegressionCaseRequest` / `AddRegressionCaseResponse` | [L143-L153](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L143-L153) | `types/dataset.ts` |
| `ApiError` class | [L155-L168](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L155-L168) | `utils/request.ts`（改为 Axios 错误适配） |
| `request` (fetch 封装) | [L170-L178](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L170-L178) | `utils/request.ts`（换 Axios 实例 + 拦截器） |
| `api.overview()` | [L181](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L181) | `api/dashboard.ts` |
| `api.versions()` | [L182](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L182) | `api/targets.ts` |
| `api.datasets()` | [L183](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L183) | `api/datasets.ts` |
| `api.evaluators()` | [L184](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L184) | `api/evaluators.ts` |
| `api.runs()` | [L185](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L185) | `api/runs.ts` |
| `api.launch()` | [L186-L200](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L186-L200) | `api/runs.ts` |
| `api.report()` | [L201](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L201) | `api/results.ts` |
| `api.rerunCase()` | [L202-L206](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L202-L206) | `api/runs.ts` |
| `api.comparison()` | [L207](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L207) | `api/results.ts` |
| `api.addCaseToRegressionDataset()` | [L208-L216](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L208-L216) | `api/datasets.ts` |
| `api.trace()` | [L217-L218](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L217-L218) | `api/trace.ts` |
| `api.validateSchema()` | [L219-L226](file:///d:\Develop\myCode_win\agentgate\web\src\api\client.ts#L219-L226) | `api/datasets.ts`（Schema 校验属 Dataset 域） |

### 10.3 现有组件迁移清单

| 现有组件 | 行数 | 迁移目标 | 说明 |
|---|---|---|---|
| [DatasetWorkspace.vue](file:///d:\Develop\myCode_win\agentgate\web\src\pages\DatasetWorkspace.vue) | - | `views/datasets/index.vue` | 入口页迁入 |
| [CaseEditor.vue](file:///d:\Develop\myCode_win\agentgate\web\src\components\dataset\CaseEditor.vue) | - | `views/datasets/components/CaseEditor.vue` | 组件迁入 |
| [CaseTable.vue](file:///d:\Develop\myCode_win\agentgate\web\src\components\dataset\CaseTable.vue) | - | `views/datasets/components/CaseTable.vue` | 组件迁入 |
| [DatasetList.vue](file:///d:\Develop\myCode_win\agentgate\web\src\components\dataset\DatasetList.vue) | - | `views/datasets/components/DatasetList.vue` | 组件迁入 |
| [ExpectationEditor.vue](file:///d:\Develop\myCode_win\agentgate\web\src\components\dataset\ExpectationEditor.vue) | - | `views/datasets/components/ExpectationEditor.vue` | 组件迁入 |
| [VersionSelector.vue](file:///d:\Develop\myCode_win\agentgate\web\src\components\dataset\VersionSelector.vue) | - | `views/datasets/components/VersionSelector.vue` | 组件迁入（注意：targets 域也会用版本选择器，若复用则提取到 `components/` 共享层） |

### 10.4 main.ts 与 style.css 迁移

| 现有文件 | 迁移目标 | 改动 |
|---|---|---|
| [main.ts](file:///d:\Develop\myCode_win\agentgate\web\src\main.ts) | `main.ts`（原地改） | 接 Pinia（`createPinia` + `pinia-plugin-persistedstate`）+ Router（`use(router)`）+ 全局样式 import |
| [style.css](file:///d:\Develop\myCode_win\agentgate\web\src\style.css) | `styles/index.scss` + `styles/reset.scss` + `styles/design-tokens/*` + `styles/element/index.scss` | 拆分：reset 归 reset.scss；Design Token 归 design-tokens/；EP 覆盖归 element/；删除原 style.css |

### 10.5 路由迁移

| 现有方式 | 迁移目标 | 改动 |
|---|---|---|
| `location.pathname` + `history.pushState` + `popstate` | `router/index.ts` + `router/modules/*.ts` | 建 10 个路由模块文件；`<router-view>` 替代 `v-if="page"`；删除 `navigate()` / `onPopState()` |
| `/` → evaluate 页 | `router/modules/runs.ts` | `path: '/runs'`，重定向 `/` → `/runs` |
| `/datasets` → datasets 页 | `router/modules/datasets.ts` | `path: '/datasets'` |
