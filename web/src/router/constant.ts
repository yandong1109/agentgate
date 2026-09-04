// 常量路由（404 等）
import type { RouteRecordRaw } from 'vue-router'

export interface AppRouteMeta {
  title?: string
  icon?: string
  hidden?: boolean
}

export const constantRoutes: RouteRecordRaw[] = [
  {
    path: '/404',
    name: 'NotFound',
    component: () => import('@/views/error/404.vue'),
    meta: { title: '页面不存在' },
  },
]
