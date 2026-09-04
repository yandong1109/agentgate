// 全局共享响应类型（对齐后端 ResponseBase<T>，待后端补齐后启用）
export interface ResponseBase<T> {
  code: string
  message: string
  data: T
}
