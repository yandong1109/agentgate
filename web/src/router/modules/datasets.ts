// Dataset 域路由
import type { RouteRecordRaw } from 'vue-router'

const datasetsRoutes: RouteRecordRaw[] = [
  {
    path: '/datasets',
    name: 'Datasets',
    component: () => import('@/views/datasets/index.vue'),
    meta: { title: '测评集管理' },
  },
]

export default datasetsRoutes
