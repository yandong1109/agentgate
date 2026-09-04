// Dashboard 域 API（Application/overview 聚合）
import { http } from '@/utils/request'
import type { Overview } from '@/types/dashboard'

export const dashboardApi = {
  overview: () => http.get<Overview>('/api/overview'),
}

export default dashboardApi
