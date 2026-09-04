<script setup lang="ts">
// 最近运行表（对标 App.vue L269-L276）
import { ElTable, ElTableColumn, ElButton, ElEmpty } from 'element-plus'
import type { Run } from '@/types/target'
import { agentLabel } from '@/utils/format'

defineProps<{ runs: Run[] }>()
const emit = defineEmits<{ open: [id: string] }>()
</script>

<template>
  <article class="report-panel">
    <div class="panel-title">
      <h3>最近运行</h3>
      <span class="panel-count">{{ runs.length }} 条</span>
    </div>
    <ElTable :data="runs" empty-text="暂无运行" size="small" :show-header="true">
      <ElTableColumn label="Agent" min-width="190">
        <template #default="scope">
          {{ agentLabel((scope.row as Run).snapshot.target) }}
        </template>
      </ElTableColumn>
      <ElTableColumn prop="status" label="状态" width="95" />
      <ElTableColumn label="操作" width="70">
        <template #default="scope">
          <ElButton link type="primary" @click="emit('open', (scope.row as Run).id)">查看</ElButton>
        </template>
      </ElTableColumn>
      <template #empty>
        <ElEmpty description="暂无运行" :image-size="60" />
      </template>
    </ElTable>
  </article>
</template>

<style scoped lang="scss">
.report-panel {
  padding: var(--spacing-xl);
  background-color: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-card);
  box-shadow: var(--elevation-1);
}

.panel-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-lg);

  h3 {
    font-size: var(--font-size-h4);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
  }
}

.panel-count {
  font-size: var(--font-size-small);
  color: var(--text-secondary);
}
</style>
