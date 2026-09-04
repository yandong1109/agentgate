<script setup lang="ts">
// Run 切换工具栏：←上一个 / 当前 Run 摘要 / 下一个→ + 运行记录按钮
// 不离开结果页即可切换 Run，运行记录按钮打开抽屉选 Run
import { computed } from 'vue'
import { ElButton, ElTag } from 'element-plus'
import { ArrowLeft, ArrowRight, List } from '@element-plus/icons-vue'
import { useDashboardStore } from '@/stores/modules/dashboard'
import { agentLabel } from '@/utils/format'
import type { Run } from '@/types/target'

const props = defineProps<{ currentRun: Run | null }>()
const emit = defineEmits<{
  switch: [id: string]
  openDrawer: []
}>()

const dashboardStore = useDashboardStore()

// 当前 Run 在 runs 列表中的索引
const currentIndex = computed(() => {
  if (!props.currentRun) return -1
  return dashboardStore.runs.findIndex((r) => r.id === props.currentRun!.id)
})

const hasPrev = computed(() => currentIndex.value > 0)
const hasNext = computed(() => {
  const runs = dashboardStore.runs
  return currentIndex.value >= 0 && currentIndex.value < runs.length - 1
})

const prevId = computed(() => (hasPrev.value ? dashboardStore.runs[currentIndex.value - 1].id : ''))
const nextId = computed(() => (hasNext.value ? dashboardStore.runs[currentIndex.value + 1].id : ''))

const runPosition = computed(() => {
  if (currentIndex.value < 0 || !dashboardStore.runs.length) return ''
  return `${currentIndex.value + 1} / ${dashboardStore.runs.length}`
})

function statusType(status: string): 'success' | 'warning' | 'info' | 'danger' {
  if (status === 'completed') return 'success'
  if (status === 'running') return 'warning'
  if (status === 'failed') return 'danger'
  return 'info'
}

function statusText(status: string): string {
  const map: Record<string, string> = {
    completed: '已完成',
    running: '运行中',
    failed: '失败',
    pending: '等待中',
    cancelled: '已取消',
  }
  return map[status] ?? status
}
</script>

<template>
  <div v-if="currentRun" class="run-toolbar">
    <ElButton
      circle
      :disabled="!hasPrev"
      :icon="ArrowLeft"
      size="default"
      @click="hasPrev && emit('switch', prevId)"
    />
    <div class="run-summary">
      <div class="run-summary-head">
        <b class="run-agent">{{ agentLabel(currentRun.snapshot.target) }}</b>
        <ElTag :type="statusType(currentRun.status)" size="small" effect="light">
          {{ statusText(currentRun.status) }}
        </ElTag>
      </div>
      <small class="run-meta">
        {{ currentRun.snapshot.dataset.dataset_name }} v{{ currentRun.snapshot.dataset.version }}
        <span v-if="runPosition" class="run-position">· {{ runPosition }}</span>
      </small>
    </div>
    <ElButton
      circle
      :disabled="!hasNext"
      :icon="ArrowRight"
      size="default"
      @click="hasNext && emit('switch', nextId)"
    />
    <ElButton :icon="List" plain @click="emit('openDrawer')">运行记录</ElButton>
  </div>
</template>

<style scoped lang="scss">
.run-toolbar {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-sm) var(--spacing-lg);
  background-color: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-card);
  box-shadow: var(--elevation-1);
}

.run-summary {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.run-summary-head {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  min-width: 0;
}

.run-agent {
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.run-meta {
  font-size: var(--font-size-small);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-position {
  color: var(--text-tertiary);
  font-family: var(--font-family-mono);
}
</style>
