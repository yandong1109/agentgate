// Targets/Integrations 域 API
import { http } from '@/utils/request'
import type {
  Capability,
  ConnectionProbe,
  PublishTargetVersionPayload,
  RegisterTargetPayload,
  TargetDetail,
  TargetListItem,
  TargetRecord,
  TargetVersionInfo,
  Version,
} from '@/types/target'

export const targetsApi = {
  // 兼容既有消费方（RunConfigPanel / dashboard / tasks / datasets），契约只增不改
  versions: () => http.get<Version[]>('/api/versions'),

  list: (type?: 'agent' | 'skill') =>
    http.get<TargetListItem[]>('/api/targets', type ? { type } : undefined),

  detail: (id: string) => http.get<TargetDetail>(`/api/targets/${id}`),

  register: (payload: RegisterTargetPayload) =>
    http.post<{ target: TargetRecord; version: TargetVersionInfo }>(
      '/api/targets',
      payload,
    ),

  update: (
    id: string,
    payload: {
      display_name?: string
      description?: string
      capabilities?: Capability[]
    },
  ) => http.patch<TargetRecord>(`/api/targets/${id}`, payload),

  remove: (id: string) =>
    http.delete<{ deleted: boolean; id: string }>(`/api/targets/${id}`),

  publishVersion: (id: string, payload: PublishTargetVersionPayload) =>
    http.post<TargetVersionInfo>(`/api/targets/${id}/versions`, payload),

  // 临时探测（注册向导中，无需先注册）
  probe: (payload: {
    endpoint: string
    credential_ref?: string | null
    timeout_seconds?: number
  }) => http.post<ConnectionProbe>('/api/targets/test-connection', payload),

  // 对已注册对象做探测（默认最新版本）
  probeTarget: (id: string, payload?: { version?: number }) =>
    http.post<ConnectionProbe>(`/api/targets/${id}/test-connection`, payload ?? {}),
}

export default targetsApi
