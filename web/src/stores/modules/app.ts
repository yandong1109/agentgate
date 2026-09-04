// 布局状态（侧边栏折叠 / 主题），persistedstate 持久化
import { defineStore } from 'pinia'

export type ThemeMode = 'light' | 'dark'
export type DeviceType = 'desktop' | 'mobile'

interface AppState {
  sidebarCollapsed: boolean
  theme: ThemeMode
  device: DeviceType
}

export const useAppStore = defineStore('app', {
  state: (): AppState => ({
    sidebarCollapsed: false,
    theme: 'light',
    device: 'desktop',
  }),
  getters: {
    sidebarWidth: (state) => (state.sidebarCollapsed ? 64 : 220),
  },
  actions: {
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed
    },
    setSidebarCollapsed(value: boolean) {
      this.sidebarCollapsed = value
    },
    setTheme(theme: ThemeMode) {
      this.theme = theme
      this.applyTheme()
    },
    toggleTheme() {
      this.setTheme(this.theme === 'light' ? 'dark' : 'light')
    },
    applyTheme() {
      const root = document.documentElement
      root.setAttribute('data-theme', this.theme)
      root.classList.toggle('dark', this.theme === 'dark')
    },
    setDevice(device: DeviceType) {
      this.device = device
    },
  },
  persist: {
    key: 'agentgate-app',
    storage: localStorage,
    paths: ['sidebarCollapsed', 'theme'],
  },
})
