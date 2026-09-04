<script setup lang="ts">
// 运行记录列表页（评测中心组·独立全宽展示，复用 RecentRunsTable）
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useDashboardStore } from '@/stores/modules/dashboard'
import PageContainer from '@/components/PageContainer.vue'
import RecentRunsTable from '@/views/results/components/RecentRunsTable.vue'

const dashboardStore = useDashboardStore()
const router = useRouter()

onMounted(async () => {
  if (!dashboardStore.runs.length) {
    try {
      await dashboardStore.refresh()
    } catch (error) {
      ElMessage.error(`无法加载运行记录：${error instanceof Error ? error.message : String(error)}`)
    }
  }
})

function openRun(id: string) {
  router.push(`/results/${id}`)
}
</script>

<template>
  <PageContainer>
    <template #heading>
      <div class="region-heading">
        <div class="region-heading-text">
          <span class="step">RUN HISTORY</span>
          <h2 class="region-title">运行记录</h2>
          <p class="region-subtitle">查看所有历史评测运行，点击查看结果报告与 Trace 下钻。</p>
        </div>
        <div class="run-count">共 {{ dashboardStore.runs.length }} 条</div>
      </div>
    </template>

    <RecentRunsTable :runs="dashboardStore.runs" @open="openRun" />
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
  padding: var(--spacing-xs) var(--spacing-md);
  background-color: var(--color-primary-lighter);
  color: var(--color-primary-active);
  border-radius: var(--radius-full);
  font-weight: var(--font-weight-medium);
}
</style>
