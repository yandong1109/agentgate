// Experiments 域路由（占位）
import type { RouteRecordRaw } from 'vue-router'

const experimentsRoutes: RouteRecordRaw[] = [
  {
    path: '/experiments',
    name: 'Experiments',
    component: () => import('@/views/experiments/index.vue'),
    meta: { title: 'A/B 实验' },
  },
]

export default experimentsRoutes
