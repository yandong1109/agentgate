<script setup lang="ts">
// 期望 vs 实际 对比面板：两栏布局，阅读顺序 = 期望xxx项符合xxx判定方式（含条件），值是什么，实际是什么
// 设计原则：
// - 期望框头部放"判定方式"徽标（算子 + 附带条件如 ±ε/校验模式）：判定方式是期望的一部分
// - 期望框体只放纯期望值；算子与条件参数（kind/epsilon/instance_mode）不混入值区
// - 实际框按结果着色（通过绿/失败红），值差异行高亮
// 期望纯化：condition dump（{"kind":"equals","expected":...}）拆解，kind→判定方式徽标，值→期望框体
// 边界处理：null→未设置 / 字段缺失→占位徽标 / 超长多行→折叠渐隐 / 长单词→anywhere 换行
import { computed, ref } from 'vue'
import { ElButton, ElTag } from 'element-plus'
import type { MethodRef, Outcome } from '@/types/result'

const props = defineProps<{
  expected: unknown
  actual: unknown
  actualMissing: boolean
  outcome: Outcome
  /** 对比算子（来自 CheckResult.methods） */
  methods?: MethodRef[]
}>()

const COLLAPSED_LINES = 6

// ---------- 算子人话映射（与创建用例时的判定动作名一致）----------
// equals→等于 / within_tolerance→数值容差 / within_range→数值范围 等 condition 名称
// 取自用例编辑器 ExpectationEditor 的下拉；contains_all/none 取自 CaseEditor 工具字段语义
const operatorText: Record<string, string> = {
  equals: '等于',
  within_tolerance: '数值容差',
  within_range: '数值范围',
  matches_pattern: '正则匹配',
  one_of: '属于集合',
  must_be_missing: '字段不存在',
  matches_json_schema: 'JSON Schema 校验',
  contains_all: '必须调用',
  contains_none: '禁止调用',
  contains_any: '包含其一',
}

function operatorLabel(name: string): string {
  return operatorText[name] ?? name
}

// ---------- 期望纯化：拆解 condition dump ----------
interface PureExpected {
  value: unknown
  /** 算子参数（如 ±0.1），显示在算子下方 */
  param: string | null
  /** 期望栏空（如 must_be_missing） */
  emptyPlaceholder: string | null
}

const CONDITION_KINDS = new Set([
  'equals',
  'within_tolerance',
  'within_range',
  'matches_pattern',
  'one_of',
  'must_be_missing',
  'matches_json_schema',
])

function isConditionDump(v: unknown): v is Record<string, unknown> {
  return (
    typeof v === 'object' &&
    v !== null &&
    !Array.isArray(v) &&
    'kind' in v &&
    typeof (v as Record<string, unknown>).kind === 'string' &&
    CONDITION_KINDS.has((v as Record<string, unknown>).kind as string)
  )
}

function extractPureExpected(expected: unknown): PureExpected {
  if (isConditionDump(expected)) {
    const kind = expected.kind as string
    switch (kind) {
      case 'equals':
        return { value: expected.expected ?? null, param: null, emptyPlaceholder: null }
      case 'within_tolerance':
        return {
          value: expected.expected ?? null,
          param: `容差 ±${expected.epsilon ?? '?'}`,
          emptyPlaceholder: null,
        }
      case 'within_range':
        return {
          value: `${expected.minimum ?? '-∞'} ~ ${expected.maximum ?? '+∞'}`,
          param: null,
          emptyPlaceholder: null,
        }
      case 'one_of':
        return { value: expected.allowed ?? null, param: null, emptyPlaceholder: null }
      case 'matches_pattern':
        return { value: `/${expected.pattern ?? ''}/`, param: null, emptyPlaceholder: null }
      case 'must_be_missing':
        return { value: null, param: null, emptyPlaceholder: '该字段应不存在' }
      case 'matches_json_schema':
        // schema 本体是期望纯值；instance_mode 是判定方式（与创建用例时的选项文案一致），归算子附带条件
        return {
          value: expected.json_schema ?? null,
          param:
            expected.instance_mode === 'json_text'
              ? '解析 JSON 文本后校验'
              : '直接校验值',
          emptyPlaceholder: null,
        }
      default:
        return { value: expected.expected ?? null, param: null, emptyPlaceholder: null }
    }
  }
  // forbidden_tool 的包装形态：{"absent_tool": "x"} → 纯值 "x"
  if (
    typeof expected === 'object' &&
    expected !== null &&
    !Array.isArray(expected) &&
    Object.keys(expected).length === 1 &&
    'absent_tool' in expected
  ) {
    return { value: (expected as Record<string, unknown>).absent_tool, param: null, emptyPlaceholder: null }
  }
  // 非条件对象（如 policy 的 {"human_review": true} 路径+值形态）或纯值：原样
  return { value: expected, param: null, emptyPlaceholder: null }
}

// 算子来源：methods → condition kind → 默认 equals
const operatorName = computed<string>(() => {
  const fromMethods = props.methods?.[0]?.operator
  if (fromMethods) return fromMethods
  if (isConditionDump(props.expected)) return (props.expected as Record<string, unknown>).kind as string
  return 'equals'
})

const pureExpected = computed(() => extractPureExpected(props.expected))

// ---------- 文本化 ----------
function formatValue(v: unknown): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'string') return v
  try {
    return JSON.stringify(v, null, 2)
  } catch {
    return String(v)
  }
}

const expectedText = computed(() => formatValue(pureExpected.value.value))
const actualText = computed(() => (props.actualMissing ? '' : formatValue(props.actual)))

const expectedEmpty = computed(
  () => pureExpected.value.value === null || pureExpected.value.value === undefined,
)
const actualEmpty = computed(
  () => props.actualMissing || props.actual === null || props.actual === undefined,
)

const isEqual = computed(
  () => !props.actualMissing && !expectedEmpty.value && expectedText.value === actualText.value,
)

// 行级对齐：期望/实际同索引不同内容标差异
interface CompareLine {
  e: string | null
  a: string | null
  diff: boolean
}

const lines = computed<CompareLine[]>(() => {
  const e = expectedText.value.split('\n')
  const a = actualText.value.split('\n')
  const n = Math.max(e.length, a.length)
  return Array.from({ length: n }, (_, i) => ({
    e: i < e.length ? e[i] : null,
    a: i < a.length ? a[i] : null,
    diff: e[i] !== a[i],
  }))
})

const isLong = computed(() => lines.value.length > COLLAPSED_LINES)
const expanded = ref(false)
const visibleLines = computed(() =>
  expanded.value || !isLong.value ? lines.value : lines.value.slice(0, COLLAPSED_LINES),
)
</script>

<template>
  <div class="compare" :class="{ 'is-collapsed': isLong && !expanded }">
    <div class="compare-grid">
      <!-- 左：期望（头部=判定方式+条件，体=纯期望值） -->
      <div class="pane pane-expected">
        <div class="pane-head">
          <span class="pane-title">期望</span>
          <span class="operator-chip" :title="pureExpected.param ?? undefined">
            <span class="operator-name">{{ operatorLabel(operatorName) }}</span>
            <small v-if="pureExpected.param" class="operator-param">{{ pureExpected.param }}</small>
          </span>
        </div>
        <div class="pane-body">
          <span v-if="expectedEmpty" class="placeholder">
            {{ pureExpected.emptyPlaceholder ?? '未设置' }}
          </span>
          <template v-else>
            <div
              v-for="(line, i) in visibleLines"
              :key="`e${i}`"
              class="line"
              :class="{ 'line-diff': line.diff }"
            >{{ line.e ?? '' }}</div>
          </template>
        </div>
      </div>

      <!-- 右：实际（按结果着色） -->
      <div
        class="pane pane-actual"
        :class="{
          'is-fail': outcome === 'fail' || outcome === 'error',
          'is-pass': outcome === 'pass',
        }"
      >
        <div class="pane-head">
          <span class="pane-title">实际</span>
          <ElTag v-if="actualMissing" type="danger" size="small" effect="plain">字段不存在</ElTag>
          <ElTag v-else-if="isEqual" type="success" size="small" effect="plain">一致</ElTag>
        </div>
        <div class="pane-body">
          <span v-if="actualEmpty" class="placeholder">无值</span>
          <template v-else>
            <div
              v-for="(line, i) in visibleLines"
              :key="`a${i}`"
              class="line"
              :class="{ 'line-diff': line.diff }"
            >{{ line.a ?? '' }}</div>
          </template>
        </div>
      </div>
    </div>

    <ElButton
      v-if="isLong"
      link
      type="primary"
      size="small"
      class="compare-toggle"
      @click="expanded = !expanded"
    >
      {{ expanded ? '收起' : `展开全部（共 ${lines.length} 行）` }}
    </ElButton>
  </div>
</template>

<style scoped lang="scss">
.compare {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs, 4px);
  min-width: 0;
}

.compare-grid {
  display: grid;
  grid-template-columns: 1fr 1fr; // 期望 | 实际
  gap: var(--spacing-sm, 8px);
  min-width: 0;

  > * {
    min-width: 0;
  }
}

.operator-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 70%; // 留出"期望"标题空间，过长省略
  padding: 1px 8px;
  border-radius: var(--radius-full, 999px);
  background-color: var(--bg-card, #fff);
  border: 1px solid var(--border-color);
  min-width: 0;
}

.operator-name {
  color: var(--text-secondary);
  font-size: var(--font-size-small, 12px);
  font-weight: var(--font-weight-semibold, 600);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.operator-param {
  color: var(--text-tertiary, #9ca3af);
  font-size: var(--font-size-small, 12px);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pane {
  display: flex;
  flex-direction: column;
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: var(--radius, 8px);
  background-color: var(--bg-card);
  overflow: hidden;
}

.pane-expected {
  .pane-title {
    color: var(--text-secondary);
  }
}

.pane-actual {
  &.is-fail {
    border-color: var(--color-danger, #ef4444);

    .pane-head {
      background-color: var(--color-danger-lighter, #fef2f2);
    }

    .pane-title {
      color: var(--color-danger, #ef4444);
    }
  }

  &.is-pass {
    border-color: var(--color-primary, #07ac8e);

    .pane-title {
      color: var(--color-primary, #07ac8e);
    }
  }
}

.pane-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-xs, 4px);
  padding: 4px 10px;
  border-bottom: 1px solid var(--border-color);
  background-color: var(--bg-muted, #f5f5f7);
  min-height: 30px;
}

.pane-title {
  font-size: var(--font-size-small, 12px);
  font-weight: var(--font-weight-semibold, 600);
}

.pane-body {
  padding: 6px 0;
  min-height: 30px; // 空值时保持面板形状稳定
  min-width: 0;
}

.placeholder {
  display: block;
  padding: 2px 10px;
  color: var(--text-tertiary, #9ca3af);
  font-style: italic;
  font-size: var(--font-size-small, 12px);
}

.line {
  font-family: var(--font-family-mono, monospace);
  font-size: var(--font-size-small, 12px);
  line-height: 20px;
  padding: 0 10px;
  white-space: pre-wrap;
  overflow-wrap: anywhere; // 超长单词/无空格串不撑破
  color: var(--text-regular, #4b5563);
}

.line-diff {
  background-color: var(--color-warning-lighter, #fef3c7);
  box-shadow: inset 2px 0 0 var(--color-warning, #f59e0b);
}

// 长内容折叠：限制高度 + 底部渐隐，视觉稳定不跳动
.is-collapsed .pane-body {
  max-height: 96px;
  overflow: hidden;
  mask-image: linear-gradient(to bottom, #000 56%, transparent);
  -webkit-mask-image: linear-gradient(to bottom, #000 56%, transparent);
}

.compare-toggle {
  align-self: center;
}

// 窄屏：两栏退化为上下堆叠（期望 → 实际）
@media (max-width: 640px) {
  .compare-grid {
    grid-template-columns: 1fr;
  }
}
</style>
