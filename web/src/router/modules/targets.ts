// Targets 域路由（占位）
import type { RouteRecordRaw } from 'vue-router'

const targetsRoutes: RouteRecordRaw[] = [
  {
    path: '/targets',
    name: 'Targets',
    component: () => import('@/views/targets/index.vue'),
    meta: { title: '评测对象' },
  },
]

export default targetsRoutes
