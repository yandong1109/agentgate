// Dataset 域 API（Case 域）—— 迁移自 web/src/api/datasets.ts，fetch → Axios
import { http, request } from '@/utils/request'
import type {
  AddRegressionCaseRequest,
  AddRegressionCaseResponse,
  DatasetDetail,
  DatasetExport,
  DatasetMutation,
  DatasetRecord,
  DatasetSummary,
  DatasetVersion,
  EvaluationCase,
  SchemaValidationResult,
  ValidationIssue,
} from '@/types/dataset'

const enc = encodeURIComponent

export const datasetsApi = {
  list: () => http.get<DatasetSummary[]>('/api/datasets'),

  create: (name: string, description = '', purpose: 'standard' | 'regression' = 'standard') =>
    http.post<DatasetMutation>('/api/datasets', { name, description, purpose }),

  detail: (datasetId: string) => http.get<DatasetDetail>(`/api/datasets/${enc(datasetId)}`),

  update: (
    datasetId: string,
    changes: Partial<Pick<DatasetRecord, 'name' | 'description' | 'archived'>>,
  ) => http.patch<DatasetRecord>(`/api/datasets/${enc(datasetId)}`, changes),

  archive: (datasetId: string) => http.delete<DatasetRecord>(`/api/datasets/${enc(datasetId)}`),

  copy: (datasetId: string, name: string, sourceVersion?: number | null) =>
    http.post<DatasetMutation>(`/api/datasets/${enc(datasetId)}/copy`, {
      name,
      source_version: sourceVersion ?? null,
    }),

  versions: (datasetId: string) =>
    http.get<DatasetVersion[]>(`/api/datasets/${enc(datasetId)}/versions`),

  version: (datasetId: string, version: number) =>
    http.get<DatasetVersion>(`/api/datasets/${enc(datasetId)}/versions/${version}`),

  currentDraft: (datasetId: string) =>
    http.get<DatasetVersion>(`/api/datasets/${enc(datasetId)}/drafts/current`),

  createDraft: (datasetId: string, basedOnVersion?: number | null) =>
    http.post<DatasetVersion>(`/api/datasets/${enc(datasetId)}/drafts`, {
      based_on_version: basedOnVersion ?? null,
    }),

  discardDraft: (datasetId: string) =>
    http.delete<void>(`/api/datasets/${enc(datasetId)}/drafts/current`),

  publish: (datasetId: string) =>
    http.post<DatasetVersion>(`/api/datasets/${enc(datasetId)}/drafts/publish`),

  addCase: (datasetId: string, item: EvaluationCase) =>
    http.post<DatasetVersion>(`/api/datasets/${enc(datasetId)}/drafts/cases`, item),

  updateCase: (datasetId: string, item: EvaluationCase) =>
    http.put<DatasetVersion>(`/api/datasets/${enc(datasetId)}/drafts/cases/${enc(item.id)}`, item),

  removeCase: (datasetId: string, caseId: string) =>
    http.delete<DatasetVersion>(`/api/datasets/${enc(datasetId)}/drafts/cases/${enc(caseId)}`),

  copyCase: (datasetId: string, caseId: string) =>
    http.post<DatasetVersion>(`/api/datasets/${enc(datasetId)}/drafts/cases/${enc(caseId)}/copy`),

  reorderCases: (datasetId: string, caseIds: string[]) =>
    http.put<DatasetVersion>(`/api/datasets/${enc(datasetId)}/drafts/case-order`, {
      case_ids: caseIds,
    }),

  exportVersion: (datasetId: string, version: number) =>
    http.get<DatasetExport>(`/api/datasets/${enc(datasetId)}/versions/${version}/export`),

  exportExcel: (datasetId: string, version: number) =>
    request<Blob>({
      url: `/api/datasets/${enc(datasetId)}/versions/${version}/export/excel`,
      method: 'GET',
      responseType: 'blob',
    }),

  excelTemplate: () =>
    request<Blob>({
      url: '/api/datasets/excel/template',
      method: 'GET',
      responseType: 'blob',
    }),

  importDataset: (payload: DatasetExport) =>
    http.post<{ dataset: DatasetRecord; version: DatasetVersion }>('/api/datasets/import', payload),

  importExcel: (file: File, name: string, description = '') => {
    const data = new FormData()
    data.append('file', file)
    data.append('name', name)
    data.append('description', description)
    return request<{ dataset: DatasetRecord; version: DatasetVersion }>({
      url: '/api/datasets/import/excel',
      method: 'POST',
      data,
    })
  },

  // 加入回归集（从 client.ts api.addCaseToRegressionDataset 迁移）
  addCaseToRegressionDataset: (runId: string, caseId: string, payload: AddRegressionCaseRequest) =>
    http.post<AddRegressionCaseResponse>(
      `/api/runs/${enc(runId)}/cases/${enc(caseId)}/regression`,
      payload,
    ),

  // JSON Schema 校验（属 Dataset 域，供 ExpectationEditor 预检）
  validateSchema: (payload: { json_schema: unknown; instance_mode?: 'structured' | 'json_text' }) =>
    http.post<SchemaValidationResult>('/api/json-schema/validate', payload),

  // 校验问题类型导出（供页面 catch 后断言）
  asValidationIssues: (detail: unknown): ValidationIssue[] =>
    Array.isArray(detail) ? (detail as ValidationIssue[]) : [],
}

export default datasetsApi
