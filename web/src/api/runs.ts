// Run 域 API（运行调度）
import { http } from '@/utils/request'
import type { Run } from '@/types/target'

export interface LaunchPayload {
  version: string
  dataset_id: string
  dataset_version: number
  evaluator_ids: string[]
}

export const runsApi = {
  runs: () => http.get<Run[]>('/api/runs'),
  launch: (payload: LaunchPayload) => http.post<Run>('/api/evaluations', payload),
  rerunCase: (runId: string, caseId: string, targetVersion?: string) =>
    http.post<Run>(`/api/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(caseId)}/rerun`, {
      target_version: targetVersion,
    }),
}

export default runsApi
