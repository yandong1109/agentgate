// 任务管理域路由
import type { RouteRecordRaw } from 'vue-router'

const tasksRoutes: RouteRecordRaw[] = [
  {
    path: '/tasks',
    name: 'Tasks',
    component: () => import('@/views/tasks/index.vue'),
    meta: { title: '任务列表' },
  },
  {
    path: '/tasks/:taskId',
    name: 'TaskDetail',
    component: () => import('@/views/tasks/TaskDetail.vue'),
    meta: { title: '任务详情' },
  },
  {
    path: '/tasks/:taskId/runs/:runId',
    name: 'RunDetail',
    component: () => import('@/views/tasks/RunDetail.vue'),
    meta: { title: '执行详情' },
  },
]

export default tasksRoutes
