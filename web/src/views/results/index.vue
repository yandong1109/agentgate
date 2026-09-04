<script setup lang="ts">
// 结果报告主视图：RunToolbar → GateBanner → MetricGrid → CheckResultList(全宽)
// 移除右侧 RecentRunsTable（消除与 /runs/history 重复），Run 切换走工具栏+抽屉
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElEmpty } from 'element-plus'
import { useResultStore } from '@/stores/modules/result'
import { useDashboardStore } from '@/stores/modules/dashboard'
import PageContainer from '@/components/PageContainer.vue'
import RunToolbar from './components/RunToolbar.vue'
import GateBanner from './components/GateBanner.vue'
import MetricGrid from './components/MetricGrid.vue'
import CheckResultList from './components/CheckResultList.vue'
import RerunComparison from './components/RerunComparison.vue'
import RerunDialog from './components/RerunDialog.vue'
import RegressionDialog from './components/RegressionDialog.vue'
import RunHistoryDrawer from './components/RunHistoryDrawer.vue'
import TraceDrawer from '@/views/trace/components/TraceDrawer.vue'

const route = useRoute()
const router = useRouter()
const resultStore = useResultStore()
const dashboardStore = useDashboardStore()

const rerunOpen = ref(false)
const rerunCaseId = ref('')
const regressionOpen = ref(false)
const regressionCaseId = ref('')
const historyDrawer = ref(false)

const report = computed(() => resultStore.report)
const caseNames = computed(() =>
  Object.fromEntries((report.value?.run.snapshot.dataset.cases ?? []).map((c) => [c.id, c.name])),
)

async function loadReport(id: string) {
  try {
    await resultStore.openRun(id)
  } catch (error) {
    ElMessage.error(`无法加载运行：${error instanceof Error ? error.message : String(error)}`)
  }
}

onMounted(async () => {
  const id = route.params.id as string | undefined
  if (id) {
    await loadReport(id)
  } else if (!resultStore.report && dashboardStore.overview.latest) {
    resultStore.setReport(dashboardStore.overview.latest)
  }
  if (!dashboardStore.runs.length) {
    try {
      await dashboardStore.refresh()
    } catch (error) {
      ElMessage.error(`无法刷新运行列表：${error instanceof Error ? error.message : String(error)}`)
    }
  }
})

watch(
  () => route.params.id,
  (id) => {
    if (id) loadReport(id as string)
  },
)

function openTrace(caseId: string) {
  resultStore.openTrace(caseId).catch((error) =>
    ElMessage.error(`无法加载 Trace：${error instanceof Error ? error.message : String(error)}`),
  )
}
function openRerun(caseId: string) {
  rerunCaseId.value = caseId
  rerunOpen.value = true
}
function openRegression(caseId: string) {
  regressionCaseId.value = caseId
  regressionOpen.value = true
}
async function onRerunSuccess() {
  rerunOpen.value = false
  await dashboardStore.refresh()
}
async function onRegressionSuccess() {
  regressionOpen.value = false
  await dashboardStore.refresh()
}
function openRun(id: string) {
  router.push(`/results/${id}`)
}
</script>

<template>
  <PageContainer>
    <template #heading>
      <div class="region-heading">
        <div class="region-heading-text">
          <h2 class="region-title">结果报告</h2>
        </div>
      </div>
    </template>

    <div v-if="report" id="result-report">
      <!-- ① Run 切换工具栏 -->
      <RunToolbar :current-run="report.run" @switch="openRun" @open-drawer="historyDrawer = true" />

      <!-- ② Gate 决策横幅 -->
      <GateBanner :gate="report.gate" />

      <!-- ③ 指标卡片 -->
      <MetricGrid :report="report" />

      <!-- ④ 检查结果（全宽，含 Tab + Case 折叠） -->
      <CheckResultList
        :report="report"
        :case-names="caseNames"
        @open-trace="openTrace"
        @open-rerun="openRerun"
        @open-regression="openRegression"
      />

      <!-- 重跑对比（条件渲染） -->
      <RerunComparison
        v-if="resultStore.comparison"
        :comparison="resultStore.comparison"
        @open-run="openRun"
      />
    </div>
    <ElEmpty v-else description="尚无结果，请先在「发起评测」页运行评估" />

    <!-- 运行记录抽屉（不离开结果页切换 Run） -->
    <RunHistoryDrawer v-if="report" v-model="historyDrawer" :runs="dashboardStore.runs" @open="openRun" />

    <RerunDialog
      :model-value="rerunOpen"
      :case-id="rerunCaseId"
      :case-name="caseNames[rerunCaseId]"
      :report="report"
      :versions="dashboardStore.versions"
      @update:model-value="(v: boolean) => (rerunOpen = v)"
      @success="onRerunSuccess"
    />

    <RegressionDialog
      :model-value="regressionOpen"
      :case-id="regressionCaseId"
      :case-name="caseNames[regressionCaseId]"
      :report="report"
      :datasets="dashboardStore.datasets"
      @update:model-value="(v: boolean) => (regressionOpen = v)"
      @success="onRegressionSuccess"
    />

    <TraceDrawer
      :model-value="resultStore.traceOpen"
      :trace="resultStore.trace"
      :case-name="resultStore.trace ? caseNames[resultStore.trace.case_id] : ''"
      @update:model-value="(v: boolean) => resultStore.closeTrace()"
    />
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
</style>
