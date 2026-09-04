<script setup lang="ts">
// 评估配置三卡：A=Agent / D=Dataset / E=Evaluators（对标 App.vue L190-L222）
// 严格按 §6.1：EP 编辑器用 :model-value + @update:modelValue，禁止 v-model
import { computed } from 'vue'
import {
  ElSelect,
  ElOption,
  ElOptionGroup,
  ElCheckboxGroup,
  ElCheckbox,
} from 'element-plus'
import { useDashboardStore } from '@/stores/modules/dashboard'
import { useRunStore } from '@/stores/modules/run'
import type { Version } from '@/types/target'

const dashboardStore = useDashboardStore()
const runStore = useRunStore()

const groupedVersions = computed<{ label: string; items: Version[] }[]>(() => {
  const groups: Record<string, { label: string; items: Version[] }> = {}
  for (const item of dashboardStore.versions) {
    const key = item.adapter_type ?? 'python_fn'
    if (!groups[key]) {
      groups[key] = { label: key === 'http' ? 'HTTP Agent' : 'Demo Agent', items: [] }
    }
    groups[key].items.push(item)
  }
  return Object.values(groups)
})

const selectedAgent = computed(() =>
  dashboardStore.versions.find((item) => item.id === runStore.selectedVersion),
)
const selectedDatasetInfo = computed(() =>
  dashboardStore.datasets.find((item) => item.id === runStore.selectedDataset),
)

function onVersionChange(value: string | number | boolean | object | null) {
  runStore.setVersion(String(value))
}
function onDatasetChange(value: string | number | boolean | object | null) {
  runStore.setDataset(String(value))
}
function onEvaluatorsChange(value: string | number | boolean | object | null) {
  runStore.setEvaluators((value as string[]) ?? [])
}
</script>

<template>
  <div class="config-grid">
    <!-- A · Agent -->
    <article class="config-card">
      <div class="card-index">A</div>
      <label class="card-label">Agent</label>
      <ElSelect
        :model-value="runStore.selectedVersion"
        data-testid="agent-select"
        aria-label="Agent 版本"
        placeholder="选择 Agent 版本"
        style="width: 100%"
        @update:model-value="onVersionChange"
      >
        <ElOptionGroup
          v-for="group in groupedVersions"
          :key="group.label"
          :label="group.label"
        >
          <ElOption
            v-for="item in group.items"
            :key="item.id"
            :label="`${item.label} · ${item.id}${item.is_latest ? '（最新）' : ''}`"
            :value="item.id"
          />
        </ElOptionGroup>
      </ElSelect>
      <p class="card-hint">
        {{ selectedAgent?.label }}，{{
          selectedAgent?.adapter_type === 'http' ? 'HTTP Agent' : '使用确定性 Provider 执行'
        }}。
      </p>
    </article>

    <!-- D · Dataset -->
    <article class="config-card">
      <div class="card-index">D</div>
      <label class="card-label">Dataset</label>
      <ElSelect
        :model-value="runStore.selectedDataset"
        data-testid="dataset-select"
        aria-label="数据集"
        placeholder="选择测评集"
        style="width: 100%"
        @update:model-value="onDatasetChange"
      >
        <ElOption
          v-for="item in dashboardStore.datasets"
          :key="item.id"
          :label="`${item.purpose === 'regression' ? '回归集 · ' : ''}${item.name} · v${item.version}`"
          :value="item.id"
        />
      </ElSelect>
      <p class="card-hint">
        {{ selectedDatasetInfo?.description }} · {{ selectedDatasetInfo?.case_count ?? 0 }} 个用例
      </p>
    </article>

    <!-- E · Evaluators -->
    <article class="config-card evaluator-card">
      <div class="card-index">E</div>
      <label class="card-label">Evaluators &amp; Metrics</label>
      <div class="evaluator-kinds" aria-label="评估器分类">
        <span class="active-kind">规则评估器</span>
        <span>LLM Judge · P2</span>
        <span>Hybrid · P2</span>
      </div>
      <ElCheckboxGroup
        :model-value="runStore.selectedEvaluators"
        class="evaluator-list"
        @update:model-value="onEvaluatorsChange"
      >
        <ElCheckbox v-for="item in dashboardStore.evaluators" :key="item.id" :value="item.id" border>
          <span class="eval-name">{{ item.name }}</span>
          <small class="eval-meta">{{ item.metric }} · {{ item.dimension }}</small>
        </ElCheckbox>
      </ElCheckboxGroup>
    </article>
  </div>
</template>

<style scoped lang="scss">
.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: var(--spacing-xl);
}

.config-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  padding: var(--spacing-xl) var(--spacing-xl) var(--spacing-lg);
  background-color: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-card);
  box-shadow: var(--elevation-1);
}

.card-index {
  position: absolute;
  top: var(--spacing-lg);
  right: var(--spacing-xl);
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-full);
  background-color: var(--color-primary-lighter);
  color: var(--color-primary-active);
  font-weight: var(--font-weight-bold);
  font-size: var(--font-size-small);
}

.card-label {
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-semibold);
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.card-hint {
  font-size: var(--font-size-small);
  color: var(--text-secondary);
  line-height: var(--line-height-base);
  margin: 0;
}

.evaluator-kinds {
  display: flex;
  gap: var(--spacing-sm);
  font-size: var(--font-size-small);

  span {
    padding: var(--spacing-xs) var(--spacing-md);
    border-radius: var(--radius-full);
    background-color: var(--gray-100);
    color: var(--text-secondary);
  }

  .active-kind {
    background-color: var(--color-primary-lighter);
    color: var(--color-primary-active);
    font-weight: var(--font-weight-medium);
  }
}

.evaluator-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--spacing-sm);

  :deep(.el-checkbox) {
    margin-right: 0;
    height: auto;
    padding: var(--spacing-sm) var(--spacing-md);
    border-radius: var(--radius);
  }
}

.eval-name {
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}

.eval-meta {
  display: block;
  font-size: var(--font-size-small);
  color: var(--text-secondary);
  margin-top: 2px;
}
</style>
