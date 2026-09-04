// 路由实例 + 守卫（NProgress）
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import NProgress from 'nprogress'
import Layout from '@/layout/index.vue'
import { constantRoutes } from './constant'
import runsRoutes from './modules/runs'
import resultsRoutes from './modules/results'
import datasetsRoutes from './modules/datasets'
import dashboardRoutes from './modules/dashboard'
import targetsRoutes from './modules/targets'
import evaluatorsRoutes from './modules/evaluators'
import optimizationRoutes from './modules/optimization'
import experimentsRoutes from './modules/experiments'
import traceRoutes from './modules/trace'
import tasksRoutes from './modules/tasks'

const layoutChildren: RouteRecordRaw[] = [
  ...runsRoutes,
  ...resultsRoutes,
  ...datasetsRoutes,
  ...dashboardRoutes,
  ...targetsRoutes,
  ...evaluatorsRoutes,
  ...optimizationRoutes,
  ...experimentsRoutes,
  ...traceRoutes,
  ...tasksRoutes,
]

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/runs' },
  {
    path: '/',
    component: Layout,
    name: 'Layout',
    children: layoutChildren,
  },
  ...constantRoutes,
  { path: '/:pathMatch(.*)*', redirect: '/404' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach((to, _from, next) => {
  NProgress.start()
  const title = (to.meta as { title?: string })?.title
  if (title) {
    document.title = `${title} · AgentGate`
  }
  next()
})

router.afterEach(() => {
  NProgress.done()
})

export default router
