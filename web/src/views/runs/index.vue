<script setup lang="ts">
// 评估配置主流程页（对标 App.vue L186-L225 评估配置区）
import { onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useDashboardStore } from '@/stores/modules/dashboard'
import { useRunStore } from '@/stores/modules/run'
import PageContainer from '@/components/PageContainer.vue'
import RunConfigPanel from './components/RunConfigPanel.vue'
import LaunchBar from './components/LaunchBar.vue'

const dashboardStore = useDashboardStore()
const runStore = useRunStore()

onMounted(async () => {
  try {
    await dashboardStore.refresh()
    runStore.resetEvaluatorsIfEmpty(dashboardStore.evaluators.map((item) => item.id))
  } catch (error) {
    ElMessage.error(`无法连接后端：${error instanceof Error ? error.message : String(error)}`)
  }
})
</script>

<template>
  <PageContainer>
    <template #heading>
      <div class="region-heading">
        <div class="region-heading-text">
          <span class="step">01 · EVALUATION SETUP</span>
          <h2 class="region-title">评估配置</h2>
          <p class="region-subtitle">选择 Agent、数据集与评估器，然后启动一次真实评估。</p>
        </div>
        <div class="run-count">已完成 {{ dashboardStore.overview.completed_runs }} 次运行</div>
      </div>
    </template>

    <RunConfigPanel />
    <LaunchBar />
  </PageContainer>
</template>

<style scoped lang="scss">
.region-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-lg);
  flex-wrap: wrap;
  width: 100%;
}

.region-heading-text {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.step {
  font-family: var(--font-family-mono);
  font-size: var(--font-size-small);
  letter-spacing: 1px;
  color: var(--color-primary);
  font-weight: var(--font-weight-semibold);
}

.region-title {
  font-size: var(--font-size-h2);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}

.region-subtitle {
  font-size: var(--font-size-body);
  color: var(--text-secondary);
}

.run-count {
  font-size: var(--font-size-small);
  color: var(--text-regular);
  padding: var(--spacing-xs) var(--spacing-md);
  background-color: var(--color-primary-lighter);
  color: var(--color-primary-active);
  border-radius: var(--radius-full);
  font-weight: var(--font-weight-medium);
}
</style>
