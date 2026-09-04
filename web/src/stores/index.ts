// Pinia 实例 + persistedstate 插件
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'

const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)

export default pinia

export * from './modules/app'
export * from './modules/dashboard'
export * from './modules/run'
export * from './modules/result'
