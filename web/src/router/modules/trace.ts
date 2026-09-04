// Trace 域路由（Trace 为结果中心内的抽屉组件库，路由重定向到结果中心）
import type { RouteRecordRaw } from 'vue-router'

const traceRoutes: RouteRecordRaw[] = [
  {
    path: '/trace',
    redirect: '/results',
  },
]

export default traceRoutes
