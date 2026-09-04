// 任务管理 API
import { http } from '@/utils/request'

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
  status: 'NEW' | 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAIL' | 'TERMINATED'
  created_at: string
  updated_at: string
  target_snapshot_id?: string
  dataset_snapshot_id?: string
  evaluator_snapshot_id?: string
  latest_run?: TaskRun
}

export interface TaskRun {
  id: string
  task_id: string
  run_no: number
  status: string
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
  status: string
  score: number
  passed: boolean
  agent_response?: string
  trace_data?: any
  evaluation_result_id?: string
  started_at?: string
  completed_at?: string
  created_at?: string
}

export interface SnapshotInfo {
  id: string
  target_id?: string
  dataset_id?: string
  evaluator_id?: string
  agent_type?: string
  snapshot_data?: any
  case_count?: number
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

export const tasksApi = {
  // 获取任务列表
  list: (params?: { status?: string; target_id?: string; page?: number; size?: number }) =>
    http.get<TaskListResponse>('/api/tasks', params),

  // 获取任务详情
  detail: (taskId: string) => http.get<Task>(`/api/tasks/${encodeURIComponent(taskId)}`),

  // 创建任务
  create: (payload: CreateTaskPayload) => http.post<Task>('/api/tasks', payload),

  // 启动任务
  start: (taskId: string) => http.post<{ task_id: string; status: string; message: string; target_snapshot_id?: string; dataset_snapshot_id?: string; evaluator_snapshot_id?: string }>(`/api/tasks/${encodeURIComponent(taskId)}/start`),

  // 停止任务
  stop: (taskId: string, reason?: string) =>
    http.post<{ task_id: string; status: string; terminated_by: string }>(`/api/tasks/${encodeURIComponent(taskId)}/stop`, { reason }),

  // 重新执行任务
  rerun: (taskId: string) => http.post<{ run_id: string; run_no: number; status: string; message: string }>(`/api/tasks/${encodeURIComponent(taskId)}/rerun`),

  // 删除任务
  delete: (taskId: string) => http.delete<void>(`/api/tasks/${encodeURIComponent(taskId)}`),

  // 获取执行记录列表
  runs: (taskId: string) => http.get<TaskRun[]>(`/api/tasks/${encodeURIComponent(taskId)}/runs`),
}

export default tasksApi
