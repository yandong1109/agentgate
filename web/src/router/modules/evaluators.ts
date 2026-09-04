// Evaluator 域路由（占位）
import type { RouteRecordRaw } from 'vue-router'

const evaluatorsRoutes: RouteRecordRaw[] = [
  {
    path: '/evaluators',
    name: 'Evaluators',
    component: () => import('@/views/evaluators/index.vue'),
    meta: { title: '评估器' },
  },
]

export default evaluatorsRoutes
