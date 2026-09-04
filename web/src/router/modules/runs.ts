// Run 域路由
import type { RouteRecordRaw } from 'vue-router'

const runsRoutes: RouteRecordRaw[] = [
  {
    path: '/runs',
    name: 'Runs',
    component: () => import('@/views/runs/index.vue'),
    meta: { title: '发起评测' },
  },
  {
    path: '/runs/history',
    name: 'RunHistory',
    component: () => import('@/views/runs/history.vue'),
    meta: { title: '运行记录' },
  },
]

export default runsRoutes
