// Optimization 域路由（占位）
import type { RouteRecordRaw } from 'vue-router'

const optimizationRoutes: RouteRecordRaw[] = [
  {
    path: '/optimization',
    name: 'Optimization',
    component: () => import('@/views/optimization/index.vue'),
    meta: { title: '调优中心' },
  },
]

export default optimizationRoutes
