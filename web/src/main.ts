import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import 'normalize.css/normalize.css'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'

import App from './App.vue'
import router from './router'
import pinia from './stores'
import './styles/index.scss'

NProgress.configure({ showSpinner: false, trickleSpeed: 200 })

const app = createApp(App)

// 注册 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(pinia)
app.use(router)
app.use(ElementPlus, { size: 'default' })

app.mount('#app')
