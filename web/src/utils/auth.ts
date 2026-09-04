// 鉴权 Token 管理（预留，对齐 redesign-plan-zh.md 术语：鉴权 Token，非 Design Token / 词元）
const TOKEN_KEY = 'agentgate_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}
