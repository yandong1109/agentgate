<script setup lang="ts">
// 启动按钮（对标 App.vue L224-L227 launch-bar）
// 调 api/runs.ts launch()，成功后跳转 /results/:id
import { ElButton, ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useDashboardStore } from '@/stores/modules/dashboard'
import { useRunStore } from '@/stores/modules/run'
import { runsApi } from '@/api/runs'

const router = useRouter()
const dashboardStore = useDashboardStore()
const runStore = useRunStore()

async function launch() {
  if (runStore.selectedEvaluators.length === 0) {
    return ElMessage.warning('请至少选择一个评估器')
  }
  const dataset = dashboardStore.datasets.find((item) => item.id === runStore.selectedDataset)
  if (dataset?.version == null) {
    return ElMessage.warning('请选择已有发布版本的测评集')
  }
  runStore.loading = true
  try {
    const run = await runsApi.launch({
      version: runStore.selectedVersion,
      dataset_id: runStore.selectedDataset,
      dataset_version: dataset.version,
      evaluator_ids: runStore.selectedEvaluators,
    })
    ElMessage.success('评估已完成，指标与证据已持久化')
    await dashboardStore.refresh()
    router.push(`/results/${run.id}`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '评估失败')
  } finally {
    runStore.loading = false
  }
}
</script>

<template>
  <div class="launch-bar">
    <div class="launch-info">
      <b>{{ runStore.selectedEvaluators.length }}</b> 个评估器已启用
      <span class="launch-sub">· 结果将写入 SQLite</span>
    </div>
    <ElButton
      type="primary"
      size="large"
      :loading="runStore.loading"
      :disabled="runStore.selectedEvaluators.length === 0"
      data-testid="launch-evaluation"
      @click="launch"
    >
      运行评估 <span class="arrow">→</span>
    </ElButton>
  </div>
</template>

<style scoped lang="scss">
.launch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-lg);
  padding: var(--spacing-lg) var(--spacing-xl);
  background-color: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-card);
  box-shadow: var(--elevation-1);
  flex-wrap: wrap;
}

.launch-info {
  font-size: var(--font-size-body);
  color: var(--text-regular);

  b {
    color: var(--color-primary);
    font-size: var(--font-size-h4);
    font-weight: var(--font-weight-bold);
  }
}

.launch-sub {
  color: var(--text-secondary);
  font-size: var(--font-size-small);
}

.arrow {
  margin-left: var(--spacing-xs);
}
</style>
