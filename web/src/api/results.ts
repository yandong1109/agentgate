// Result 域 API（结果中心）
import { http } from '@/utils/request'
import type { Report, RerunComparison } from '@/types/result'

export const resultsApi = {
  report: (id: string) => http.get<Report>(`/api/runs/${encodeURIComponent(id)}`),
  comparison: (runId: string) =>
    http.get<RerunComparison>(`/api/runs/${encodeURIComponent(runId)}/comparison`),
}

export default resultsApi
