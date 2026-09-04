<script setup lang="ts">
// 总览看板：展示后端 overview 已支持的核心指标（运行数/已完成/用例数/最近运行）
// 门禁通过率/失败分布/趋势为平台级聚合指标，后端 overview 尚未提供，置 P2 占位，
// 待后端聚合接口就绪后接入。视图只消费 Overview 已定义字段 + Report.run.id。
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElCard, ElEmpty, ElTag, ElButton } from 'element-plus'
import PageContainer from '@/components/PageContainer.vue'
import { useDashboardStore } from '@/stores/modules/dashboard'

const router = useRouter()
const dashboardStore = useDashboardStore()
const overview = computed(() => dashboardStore.overview)

const totalRuns = computed(() => overview.value.total_runs ?? 0)
const completedRuns = computed(() => overview.value.completed_runs ?? 0)
const caseCount = computed(() => overview.value.case_count ?? 0)
const latest = computed(() => overview.value.latest)
const latestRunId = computed(() => latest.value?.run.id ?? '')

function goLatestResult() {
  if (latestRunId.value) router.push(`/results/${latestRunId.value}`)
}
</script>

<template>
  <PageContainer title="总览" description="AgentGate 评测平台核心指标看板。">
    <template #extra>
      <ElButton @click="$router.push('/runs/history')">运行记录</ElButton>
      <ElButton type="primary" @click="$router.push('/runs')">发起评测</ElButton>
    </template>

    <div class="dashboard-grid">
      <!-- 运行概览（真实指标） -->
      <ElCard class="dashboard-card" shadow="never">
        <template #header>
          <div class="card-header">
            <h3>运行概览</h3>
            <ElButton v-if="latestRunId" link type="primary" @click="goLatestResult">查看最近结果</ElButton>
          </div>
        </template>
        <div class="stat-grid">
          <div class="stat-item">
            <div class="stat-value">{{ totalRuns }}</div>
            <div class="stat-label">总运行数</div>
          </div>
          <div class="stat-item">
            <div class="stat-value is-success">{{ completedRuns }}</div>
            <div class="stat-label">已完成</div>
          </div>
        </div>
      </ElCard>

      <!-- 资产概览（真实指标） -->
      <ElCard class="dashboard-card" shadow="never">
        <template #header><h3>资产概览</h3></template>
        <div class="stat-grid">
          <div class="stat-item">
            <div class="stat-value">{{ caseCount }}</div>
            <div class="stat-label">用例数</div>
          </div>
          <div class="stat-item">
            <div class="stat-value is-muted">P2</div>
            <div class="stat-label">累计指标</div>
          </div>
        </div>
      </ElCard>
    </div>

    <!-- 门禁通过率（P2：后端 overview 暂无平台级门禁聚合） -->
    <ElCard class="dashboard-card" shadow="never">
      <template #header>
        <div class="card-header">
          <h3>门禁通过率</h3>
          <ElTag type="info" size="small" effect="plain">P2</ElTag>
        </div>
      </template>
      <ElEmpty description="平台级门禁聚合通过率将在 P2 阶段接入后端 overview 聚合接口后展示。" :image-size="60" />
    </ElCard>

    <!-- 失败分布（P2：后端 overview 暂无失败标签聚合） -->
    <ElCard class="dashboard-card" shadow="never">
      <template #header>
        <div class="card-header">
          <h3>失败分布</h3>
          <ElTag type="info" size="small" effect="plain">P2</ElTag>
        </div>
      </template>
      <ElEmpty description="失败标签分布将在 P2 阶段接入后端聚合接口后展示。" :image-size="60" />
    </ElCard>

    <!-- 趋势看板（P2：后端多 Run 聚合接口就绪后接入） -->
    <ElCard class="dashboard-card" shadow="never">
      <template #header>
        <div class="card-header">
          <h3>趋势看板</h3>
          <ElTag type="info" size="small" effect="plain">P2</ElTag>
        </div>
      </template>
      <ElEmpty
        description="门禁通过率趋势 / 回归集统计趋势，将在 P2 阶段接入后端多 Run 聚合接口后展示。"
        :image-size="60"
      />
    </ElCard>
  </PageContainer>
</template>

<style scoped lang="scss">
.dashboard-card {
  margin-bottom: var(--spacing-lg, 16px);

  :deep(.el-card__header) {
    padding: var(--spacing-md, 12px) var(--spacing-lg, 16px);
    border-bottom: 1px solid var(--border-color);

    h3 {
      margin: 0;
      font-size: var(--font-size-body, 14px);
      font-weight: var(--font-weight-semibold, 600);
      color: var(--text-primary);
    }
  }

  :deep(.el-card__body) {
    padding: var(--spacing-lg, 16px);
  }
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: var(--spacing-lg, 16px);
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-lg, 16px);
  text-align: center;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-xs, 4px);
}

.stat-value {
  font-size: 22px;
  font-weight: var(--font-weight-bold, 700);
  color: var(--text-primary);
  line-height: 1.2;

  &.is-success {
    color: var(--color-primary, #07ac8e);
  }

  &.is-muted {
    color: var(--text-secondary);
    font-size: var(--font-size-small, 12px);
    font-weight: var(--font-weight-regular, 400);
  }
}

.stat-label {
  font-size: var(--font-size-small, 12px);
  color: var(--text-secondary);
}
</style>
