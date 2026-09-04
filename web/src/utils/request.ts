// Axios 实例 + 拦截器（禁止 new Axios / fetch，统一走 @/utils/request）
import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse } from 'axios'
import { getToken } from './auth'

/** 复刻 client.ts 的 ApiError 逻辑（status + detail） */
export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown) {
    super(
      Array.isArray(detail)
        ? detail.map((item) => (item as { message?: string })?.message ?? JSON.stringify(item)).join('；')
        : String(detail ?? `HTTP ${status}`),
    )
    this.status = status
    this.detail = detail
    this.name = 'ApiError'
  }
}

const service: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '',
  timeout: 30000,
})

// 请求拦截器：注入鉴权 Token（预留）
service.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      config.headers = config.headers ?? {}
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// 响应拦截器：兼容现有裸 JSON（后端未补齐 ResponseBase，先直接返回 data）
service.interceptors.response.use(
  (response: AxiosResponse) => {
    const data = response.data
    // 适配未来 ResponseBase<T>：{ code, message, data }
    if (
      data &&
      typeof data === 'object' &&
      'code' in data &&
      'message' in data &&
      'data' in data
    ) {
      if (data.code === '0' || data.code === 0) return data.data
      return Promise.reject(new ApiError(200, data.message))
    }
    return data
  },
  (error) => {
    const status = error?.response?.status ?? 0
    const detail = error?.response?.data?.detail ?? error?.message ?? `HTTP ${status}`
    return Promise.reject(new ApiError(status, detail))
  },
)

export default service

/** 通用请求函数，返回后端业务数据 */
export function request<T = unknown>(config: AxiosRequestConfig): Promise<T> {
  return service.request<unknown, T>(config)
}

/** 便捷方法 */
export const http = {
  get: <T = unknown>(url: string, params?: Record<string, unknown>) =>
    request<T>({ url, method: 'GET', params }),
  post: <T = unknown>(url: string, data?: unknown) =>
    request<T>({ url, method: 'POST', data, headers: { 'Content-Type': 'application/json' } }),
  put: <T = unknown>(url: string, data?: unknown) =>
    request<T>({ url, method: 'PUT', data, headers: { 'Content-Type': 'application/json' } }),
  patch: <T = unknown>(url: string, data?: unknown) =>
    request<T>({ url, method: 'PATCH', data, headers: { 'Content-Type': 'application/json' } }),
  delete: <T = unknown>(url: string) => request<T>({ url, method: 'DELETE' }),
}

export { service as axiosInstance }
