// Trace 域 API
import { http } from '@/utils/request'
import type { Trace } from '@/types/trace'

export const traceApi = {
  trace: (runId: string, caseId: string) =>
    http.get<Trace>(`/api/runs/${encodeURIComponent(runId)}/traces/${encodeURIComponent(caseId)}`),
}

export default traceApi
