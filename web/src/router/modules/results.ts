// Result 域路由
import type { RouteRecordRaw } from 'vue-router'

const resultsRoutes: RouteRecordRaw[] = [
  {
    path: '/results/:id?',
    name: 'Results',
    component: () => import('@/views/results/index.vue'),
    meta: { title: '结果报告' },
  },
]

export default resultsRoutes
