// Dashboard 域路由（占位）
import type { RouteRecordRaw } from 'vue-router'

const dashboardRoutes: RouteRecordRaw[] = [
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/dashboard/index.vue'),
    meta: { title: '总览' },
  },
]

export default dashboardRoutes
