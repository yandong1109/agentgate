<script setup lang="ts">
// 期望结果编辑器（迁移自 web/src/components/dataset/ExpectationEditor.vue）
// §6.1：EP 组件用 :model-value + @update:modelValue，禁止 v-model
import { onBeforeUnmount, ref, watch } from 'vue'
import {
  ElButton,
  ElDropdown,
  ElDropdownMenu,
  ElDropdownItem,
  ElInput,
  ElInputNumber,
  ElSelect,
  ElOption,
  ElEmpty,
} from 'element-plus'
import { datasetsApi } from '@/api/datasets'
import type { Expectation } from '@/types/dataset'

/* eslint-disable @typescript-eslint/no-explicit-any */
const props = defineProps<{ modelValue: Expectation[]; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: Expectation[]] }>()

const rows = ref<any[]>([])
let syncing = false
const cloneJson = <T>(value: T): T => JSON.parse(JSON.stringify(value))
const schemaTexts = ref<Record<string, string>>({})
const schemaErrors = ref<Record<string, string | null>>({})
const schemaPreflightErrors = ref<Record<string, string | null>>({})
const preflightTimers = new Map<string, ReturnType<typeof setTimeout>>()
const PREFLIGHT_DEBOUNCE_MS = 400

watch(
  () => props.modelValue,
  (value) => {
    syncing = true
    rows.value = cloneJson(value ?? [])
    schemaTexts.value = {}
    schemaErrors.value = {}
    schemaPreflightErrors.value = {}
    queueMicrotask(() => {
      syncing = false
    })
  },
  { immediate: true, deep: true },
)
watch(
  rows,
  (value) => {
    if (!syncing) emit('update:modelValue', cloneJson(value))
  },
  { deep: true },
)

const uuid = () => crypto.randomUUID()
const condition = (kind = 'equals'): any => {
  if (kind === 'equals') return { kind, expected: '' }
  if (kind === 'within_tolerance') return { kind, expected: 0, epsilon: 0.000001 }
  if (kind === 'within_range') return { kind, minimum: null, maximum: null }
  if (kind === 'matches_pattern') return { kind, pattern: '' }
  if (kind === 'one_of') return { kind, allowed: [] }
  if (kind === 'matches_json_schema')
    return { kind, json_schema: {}, instance_mode: 'structured' }
  return { kind: 'must_be_missing' }
}

function add(kind: 'state' | 'tool_argument' | 'output' = 'state') {
  const base: any = { id: uuid(), kind, name: null, path: '', condition: condition() }
  if (kind === 'tool_argument') Object.assign(base, { tool: '', occurrence: 'last' })
  if (kind === 'output') base.path = null
  rows.value.push(base)
}

function changeKind(index: number, kind: string) {
  const current = rows.value[index]
  const next: any = {
    id: current.id,
    kind,
    name: current.name,
    path: kind === 'output' ? null : current.path ?? '',
    condition: current.condition,
  }
  if (kind === 'tool_argument')
    Object.assign(next, {
      tool: current.tool ?? '',
      occurrence: current.occurrence ?? 'last',
    })
  rows.value[index] = next
}

function changeCondition(row: any, kind: string) {
  row.condition = condition(kind)
  schemaTexts.value[row.id] = ''
  schemaErrors.value[row.id] = null
  schemaPreflightErrors.value[row.id] = null
  const timer = preflightTimers.get(row.id)
  if (timer) {
    clearTimeout(timer)
    preflightTimers.delete(row.id)
  }
}

function asJson(value: unknown) {
  return JSON.stringify(value ?? '', null, 0)
}

function setJson(row: any, field: string, value: string) {
  try {
    row.condition[field] = JSON.parse(value)
  } catch {
    row.condition[field] = value
  }
}

function schemaText(row: any): string {
  const cached = schemaTexts.value[row.id]
  if (cached !== undefined) return cached
  const schema = row.condition?.json_schema
  if (
    schema &&
    typeof schema === 'object' &&
    !Array.isArray(schema) &&
    Object.keys(schema).length > 0
  ) {
    return JSON.stringify(schema, null, 2)
  }
  return ''
}

function schemaError(row: any): string | null {
  return schemaErrors.value[row.id] ?? null
}

function preflightError(row: any): string | null {
  return schemaPreflightErrors.value[row.id] ?? null
}

function clearPreflight(row: any) {
  schemaPreflightErrors.value[row.id] = null
  const timer = preflightTimers.get(row.id)
  if (timer) {
    clearTimeout(timer)
    preflightTimers.delete(row.id)
  }
}

function schedulePreflight(row: any) {
  clearPreflight(row)
  const timer = setTimeout(() => {
    void runPreflight(row)
  }, PREFLIGHT_DEBOUNCE_MS)
  preflightTimers.set(row.id, timer)
}

async function runPreflight(row: any) {
  const schema = row.condition?.json_schema
  if (!schema || typeof schema !== 'object' || Array.isArray(schema)) return
  const instanceMode = row.condition?.instance_mode ?? 'structured'
  try {
    const result = await datasetsApi.validateSchema({
      json_schema: schema,
      instance_mode: instanceMode,
    })
    schemaPreflightErrors.value[row.id] = result.valid
      ? null
      : result.errors[0]?.message ?? 'Schema 校验未通过'
  } catch {
    schemaPreflightErrors.value[row.id] = null
  }
}

function setSchema(row: any, value: string) {
  schemaTexts.value[row.id] = value
  if (value.trim() === '') {
    schemaErrors.value[row.id] = null
    clearPreflight(row)
    return
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(value)
  } catch (e: any) {
    schemaErrors.value[row.id] = `JSON 格式错误：${e.message}`
    clearPreflight(row)
    return
  }
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    schemaErrors.value[row.id] = 'JSON Schema 顶层必须是对象，不能是数组或标量'
    clearPreflight(row)
    return
  }
  schemaErrors.value[row.id] = null
  row.condition.json_schema = parsed
  schedulePreflight(row)
}

onBeforeUnmount(() => {
  for (const timer of preflightTimers.values()) clearTimeout(timer)
  preflightTimers.clear()
})

function allowedText(row: any) {
  return (row.condition.allowed ?? [])
    .map((item: unknown) => (typeof item === 'string' ? item : JSON.stringify(item)))
    .join(', ')
}

function setAllowed(row: any, value: string) {
  row.condition.allowed = value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      try {
        return JSON.parse(item)
      } catch {
        return item
      }
    })
}

function removeRow(index: number) {
  rows.value.splice(index, 1)
}
/* eslint-enable @typescript-eslint/no-explicit-any */
</script>

<template>
  <div class="expectation-editor">
    <div class="subsection-heading">
      <div>
        <b>期望结果</b>
        <small>系统会把每一项期望与真实 Trace、状态或输出比较。</small>
      </div>
      <ElDropdown v-if="!disabled" trigger="click" @command="add">
        <ElButton size="small" data-testid="add-expectation">添加期望</ElButton>
        <template #dropdown>
          <ElDropdownMenu>
            <ElDropdownItem command="state">最终状态</ElDropdownItem>
            <ElDropdownItem command="tool_argument">工具参数</ElDropdownItem>
            <ElDropdownItem command="output">最终输出</ElDropdownItem>
          </ElDropdownMenu>
        </template>
      </ElDropdown>
    </div>

    <div
      v-for="(row, index) in rows"
      :key="row.id"
      class="expectation-row"
      :data-testid="`expectation-${index}`"
    >
      <div class="expectation-row-head">
        <ElSelect
          :model-value="row.kind"
          :disabled="disabled"
          size="small"
          @update:model-value="(v: any) => changeKind(index, v)"
        >
          <ElOption label="最终状态" value="state" />
          <ElOption label="工具参数" value="tool_argument" />
          <ElOption label="最终输出" value="output" />
        </ElSelect>
        <ElInput
          :model-value="row.name"
          :disabled="disabled"
          size="small"
          placeholder="检查名称（可选）"
          @update:model-value="(v: any) => (row.name = v)"
        />
        <ElButton v-if="!disabled" link type="danger" @click="removeRow(Number(index))">
          删除
        </ElButton>
      </div>
      <div class="expectation-fields">
        <ElInput
          v-if="row.kind === 'tool_argument'"
          :model-value="row.tool"
          :disabled="disabled"
          :data-testid="`expectation-tool-${index}`"
          placeholder="工具名，例如 approve_loan"
          @update:model-value="(v: any) => (row.tool = v)"
        />
        <ElInput
          :model-value="row.path"
          :disabled="disabled"
          :data-testid="`expectation-path-${index}`"
          :placeholder="row.kind === 'output' ? '输出路径（留空表示完整输出）' : '字段路径，例如 status'"
          @update:model-value="(v: any) => (row.path = v)"
        />
        <ElSelect
          v-if="row.kind === 'tool_argument'"
          :model-value="row.occurrence"
          :disabled="disabled"
          @update:model-value="(v: any) => (row.occurrence = v)"
        >
          <ElOption label="最后一次调用" value="last" />
          <ElOption label="第一次调用" value="first" />
          <ElOption label="任意一次通过" value="any" />
          <ElOption label="所有调用通过" value="all" />
        </ElSelect>
        <ElSelect
          :model-value="row.condition.kind"
          :disabled="disabled"
          :data-testid="`expectation-condition-${index}`"
          @update:model-value="(v: any) => changeCondition(row, v)"
        >
          <ElOption label="等于" value="equals" />
          <ElOption label="数值容差" value="within_tolerance" />
          <ElOption label="数值范围" value="within_range" />
          <ElOption label="正则匹配" value="matches_pattern" />
          <ElOption label="属于集合" value="one_of" />
          <ElOption label="字段不存在" value="must_be_missing" />
          <ElOption label="JSON Schema 校验" value="matches_json_schema" />
        </ElSelect>
        <ElInput
          v-if="row.condition.kind === 'equals'"
          :model-value="asJson(row.condition.expected)"
          :disabled="disabled"
          :data-testid="`expectation-value-${index}`"
          placeholder="期望值，支持 JSON"
          @update:model-value="(v: any) => setJson(row, 'expected', v)"
        />
        <template v-else-if="row.condition.kind === 'within_tolerance'">
          <ElInputNumber
            :model-value="row.condition.expected"
            :disabled="disabled"
            placeholder="期望值"
            @update:model-value="(v: any) => (row.condition.expected = v)"
          />
          <ElInputNumber
            :model-value="row.condition.epsilon"
            :disabled="disabled"
            :min="0.000000001"
            placeholder="容差"
            @update:model-value="(v: any) => (row.condition.epsilon = v)"
          />
        </template>
        <template v-else-if="row.condition.kind === 'within_range'">
          <ElInputNumber
            :model-value="row.condition.minimum"
            :disabled="disabled"
            placeholder="最小值"
            @update:model-value="(v: any) => (row.condition.minimum = v)"
          />
          <ElInputNumber
            :model-value="row.condition.maximum"
            :disabled="disabled"
            placeholder="最大值"
            @update:model-value="(v: any) => (row.condition.maximum = v)"
          />
        </template>
        <ElInput
          v-else-if="row.condition.kind === 'matches_pattern'"
          :model-value="row.condition.pattern"
          :disabled="disabled"
          placeholder="正则表达式"
          @update:model-value="(v: any) => (row.condition.pattern = v)"
        />
        <ElInput
          v-else-if="row.condition.kind === 'one_of'"
          :model-value="allowedText(row)"
          :disabled="disabled"
          placeholder="允许值，逗号分隔"
          @update:model-value="(v: any) => setAllowed(row, v)"
        />
        <div v-else-if="row.condition.kind === 'matches_json_schema'" class="schema-field">
          <ElInput
            type="textarea"
            :rows="3"
            :model-value="schemaText(row)"
            :disabled="disabled"
            :data-testid="`expectation-schema-${index}`"
            placeholder='输入 JSON Schema 对象，如 {"type":"object","required":["id"]}'
            @update:model-value="(v: any) => setSchema(row, v)"
          />
          <div
            v-if="schemaError(row)"
            class="schema-error"
            :data-testid="`expectation-schema-error-${index}`"
          >
            {{ schemaError(row) }}
          </div>
          <div
            v-else-if="preflightError(row)"
            :data-testid="`expectation-schema-preflight-error-${index}`"
            class="schema-preflight-error"
          >
            {{ preflightError(row) }}
          </div>
          <ElSelect
            :model-value="row.condition.instance_mode ?? 'structured'"
            :disabled="disabled"
            :data-testid="`expectation-instance-mode-${index}`"
            @update:model-value="(v: any) => (row.condition.instance_mode = v)"
          >
            <ElOption label="直接校验值 (structured)" value="structured" />
            <ElOption label="解析 JSON 文本后校验 (json_text)" value="json_text" />
          </ElSelect>
        </div>
        <div v-else class="expectation-unknown">
          <small>未知条件类型：{{ row.condition.kind }}</small>
        </div>
      </div>
    </div>
    <ElEmpty v-if="!rows.length" description="暂无字段、状态或输出期望" :image-size="58" />
  </div>
</template>

<style scoped lang="scss">
.expectation-editor {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.subsection-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm);

  b {
    color: var(--text-primary);
    font-size: var(--font-size-body);
  font-weight: var(--font-weight-semibold);
  margin-right: var(--spacing-xs);
  }

  small {
    color: var(--text-secondary);
    font-size: var(--font-size-small);
  }
}

.expectation-row {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  padding: var(--spacing-sm);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  background: var(--bg-subtle);
}

.expectation-row-head {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);

  .el-select {
    width: 140px;
    flex-shrink: 0;
  }

  .el-input {
    flex: 1;
  }
}

.expectation-fields {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: var(--spacing-xs);

  > .el-input,
  > .el-select,
  > .el-input-number {
    flex: 1;
    min-width: 140px;
  }
}

.schema-field {
  flex-basis: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);

  .el-select {
    width: 100%;
  }
}

.schema-error,
.schema-preflight-error {
  color: var(--color-error);
  font-size: var(--font-size-small);
  margin-top: var(--spacing-xs);
}

.expectation-unknown small {
  font-size: var(--font-size-small);
  color: var(--text-secondary);
}
</style>
