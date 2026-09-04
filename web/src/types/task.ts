// 任务管理类型定义
export interface Task {
  id: string
  task_name: string
  target_id: string
  target_name?: string
  target_type?: string
  dataset_id: string
  dataset_name?: string
  evaluator_id: string
  evaluator_name?: string
  evaluator_type?: string
  status: TaskStatus
  created_at: string
  updated_at: string
  target_snapshot_id?: string
  dataset_snapshot_id?: string
  evaluator_snapshot_id?: string
  latest_run?: TaskRun
}

export type TaskStatus = 'NEW' | 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAIL' | 'TERMINATED'

export interface TaskRun {
  id: string
  task_id: string
  run_no: number
  status: TaskStatus
  target_snapshot_id?: string
  dataset_snapshot_id?: string
  evaluator_snapshot_id?: string
  total_cases: number
  completed_cases: number
  passed_cases: number
  failed_cases: number
  avg_score: number
  pass_rate: number
  started_at: string | null
  completed_at: string | null
  terminated_by?: string
  error_message?: string
  created_at?: string
}

export interface CaseExecution {
  id: string
  run_id: string
  case_id: string
  status: TaskStatus
  score: number
  passed: boolean
  agent_response?: string
  trace_data?: any
  evaluation_result_id?: string
  started_at?: string
  completed_at?: string
  created_at?: string
}

export interface TaskListResponse {
  content: Task[]
  total_elements: number
  total_pages: number
  page: number
  size: number
}

export interface CreateTaskPayload {
  task_name: string
  target_id: string
  dataset_id: string
  evaluator_id: string
}

export interface TargetOption {
  id: string
  agent_name: string
  agent_type: string
  status: string
}

export interface DatasetOption {
  id: string
  name: string
  description: string
  case_count?: number
}

export interface EvaluatorOption {
  id: string
  name: string
  evaluator_type: string
}

// 快照信息
export interface SnapshotInfo {
  id: string
  target_id?: string
  dataset_id?: string
  evaluator_id?: string
  agent_type?: string
  snapshot_data?: any
  case_count?: number
}
