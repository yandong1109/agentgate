// Dashboard 域状态（overview/versions/datasets/evaluators/runs 聚合）
// 对齐 App.vue L7-L11 + refresh()
//
// 采用 setup store：overview.latest 含 Report→Run→DatasetVersion→Condition（JsonValue 递归）
// 的深嵌套类型，options store 会对 state 做 UnwrapRef 深解包导致类型递归爆炸（TS2589）。
// setup store 的 state 为浅解包；对含深嵌套的 overview/runs 用 shallowRef，
// 让 UnwrapRef 止于表层，既根治 TS2589 又保持响应式（数据整体替换）。
import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'
import { dashboardApi } from '@/api/dashboard'
import { targetsApi } from '@/api/targets'
import { datasetsApi } from '@/api/datasets'
import { evaluatorsApi } from '@/api/evaluators'
import { runsApi } from '@/api/runs'
import { useRunStore } from '@/stores/modules/run'
import type { Overview } from '@/types/dashboard'
import type { Version } from '@/types/target'
import type { DatasetSummary } from '@/types/dataset'
import type { EvaluatorOption } from '@/types/evaluator'
import type { Run } from '@/types/target'

export const useDashboardStore = defineStore('dashboard', () => {
  const runStore = useRunStore()
  const overview = shallowRef<Overview>({
    total_runs: 0,
    completed_runs: 0,
    case_count: 0,
    latest: null,
  })
  const versions = ref<Version[]>([])
  const datasets = ref<DatasetSummary[]>([])
  const evaluators = ref<EvaluatorOption[]>([])
  const runs = shallowRef<Run[]>([])
  const loading = ref(false)

  async function refresh() {
    loading.value = true
    try {
      const [overviewData, versionsData, datasetsData, evaluatorsData, runsData] = await Promise.all([
        dashboardApi.overview(),
        targetsApi.versions(),
        datasetsApi.list(),
        evaluatorsApi.evaluators(),
        runsApi.runs(),
      ])
      overview.value = overviewData
      versions.value = versionsData
      runStore.ensureVersionExists(versionsData)
      datasets.value = datasetsData
      evaluators.value = evaluatorsData
      runs.value = runsData
    } finally {
      loading.value = false
    }
  }

  return { overview, versions, datasets, evaluators, runs, loading, refresh }
})
