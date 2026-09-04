// Dashboard 域类型
import type { Report } from './result'

export interface Overview {
  total_runs: number
  completed_runs: number
  case_count: number
  latest: Report | null
}
