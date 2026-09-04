// Result 域状态（report/trace/comparison）
// 对齐 App.vue L15-L17 + openRun/openTrace
//
// 采用 setup store + shallowRef：report(Report→Run→JsonValue 递归)、
// trace(Trace→JsonObject 递归) 均为深嵌套类型，options store 的 UnwrapRef 深解包
// 会触发 TS2589；shallowRef 让解包止于表层，数据整体替换时仍触发响应。
import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'
import { resultsApi } from '@/api/results'
import { traceApi } from '@/api/trace'
import type { Report, RerunComparison } from '@/types/result'
import type { Trace } from '@/types/trace'

export const useResultStore = defineStore('result', () => {
  const report = shallowRef<Report | null>(null)
  const trace = shallowRef<Trace | null>(null)
  const comparison = shallowRef<RerunComparison | null>(null)
  const traceOpen = ref(false)

  function setReport(next: Report | null) {
    report.value = next
  }

  async function openRun(id: string) {
    const nextReport = await resultsApi.report(id)
    report.value = nextReport
    trace.value = null
    comparison.value = nextReport.run.parent_run_id
      ? await resultsApi.comparison(id)
      : null
  }

  async function openTrace(caseId: string) {
    const current = report.value
    if (!current) return
    trace.value = await traceApi.trace(current.run.id, caseId)
    traceOpen.value = true
  }

  function closeTrace() {
    traceOpen.value = false
  }

  function setComparison(next: RerunComparison | null) {
    comparison.value = next
  }

  return { report, trace, comparison, traceOpen, setReport, openRun, openTrace, closeTrace, setComparison }
})
