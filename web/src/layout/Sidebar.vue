<script setup lang="ts">
// 侧菜单：4 组 + 总览（UCD 信息架构，对齐 redesign-plan-zh.md §5.2.1）
// 文件层按 owner 域分，菜单层按用户任务工作流分组
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMenu, ElMenuItem, ElSubMenu, ElIcon } from 'element-plus'
import {
  Odometer,
  Connection,
  Files,
  DataLine,
  VideoPlay,
  Document,
  TrendCharts,
  Aim,
  Folder,
  List,
  List as TaskIcon,
} from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/modules/app'
import type { Component } from 'vue'

interface MenuItem {
  index: string
  label: string
  icon: Component
  testid?: string
}
interface MenuGroup {
  key: string
  title: string
  icon: Component
  children: MenuItem[]
}

const route = useRoute()
const appStore = useAppStore()

// 顶级单项（总览/调优/实验对比）
const topItems: MenuItem[] = [{ index: '/dashboard', label: '总览', icon: Odometer }]

// 分组（资产管理 / 评测中心 / 任务管理）
const groups: MenuGroup[] = [
  {
    key: 'assets',
    title: '资产管理',
    icon: Folder,
    children: [
      { index: '/datasets', label: '测评集', icon: Files, testid: 'nav-datasets' },
      { index: '/evaluators', label: '评估器', icon: DataLine },
    ],
  },
  {
    key: 'evaluation',
    title: '评测中心',
    icon: VideoPlay,
    children: [
      { index: '/targets', label: '评测对象', icon: Connection },
      { index: '/runs', label: '发起评测', icon: VideoPlay, testid: 'nav-evaluate' },
      { index: '/runs/history', label: '运行记录', icon: List },
      { index: '/results', label: '结果报告', icon: Document },
    ],
  },
  {
    key: 'task',
    title: '任务管理',
    icon: TaskIcon,
    children: [
      { index: '/tasks', label: '任务列表', icon: TaskIcon },
    ],
  },
]

// 底部顶级单项
const bottomItems: MenuItem[] = [
  { index: '/optimization', label: '调优', icon: TrendCharts },
  { index: '/experiments', label: '实验对比', icon: Aim },
]

// 高亮当前菜单项（处理 /results/:id → /results、/runs/history 独立匹配）
const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/runs/history')) return '/runs/history'
  if (path.startsWith('/runs')) return '/runs'
  if (path.startsWith('/results')) return '/results'
  if (path.startsWith('/tasks')) return '/tasks'
  return path
})

// 展开的子菜单：资产管理 + 评测中心 + 任务管理三组默认展开，主流程入口均直达
const defaultOpeneds = computed(() => ['evaluation', 'assets', 'task'])

const asideWidth = computed(() => (appStore.sidebarCollapsed ? '64px' : '220px'))
</script>

<template>
  <aside class="sidebar" :style="{ width: asideWidth }">
    <ElMenu
      :default-active="activeMenu"
      :default-openeds="defaultOpeneds"
      :collapse="appStore.sidebarCollapsed"
      :collapse-transition="false"
      :unique-opened="true"
      router
      class="sidebar-menu"
      background-color="transparent"
      text-color="var(--text-regular)"
      active-text-color="var(--color-primary)"
    >
      <!-- 顶级：总览 -->
      <ElMenuItem v-for="item in topItems" :key="item.index" :index="item.index">
        <ElIcon><component :is="item.icon" /></ElIcon>
        <template #title>{{ item.label }}</template>
      </ElMenuItem>

      <!-- 分组：资产管理 / 评测中心 -->
      <ElSubMenu v-for="group in groups" :key="group.key" :index="group.key">
        <template #title>
          <ElIcon><component :is="group.icon" /></ElIcon>
          <span>{{ group.title }}</span>
        </template>
        <ElMenuItem
          v-for="child in group.children"
          :key="child.index"
          :index="child.index"
          :data-testid="child.testid"
        >
          <ElIcon><component :is="child.icon" /></ElIcon>
          <template #title>{{ child.label }}</template>
        </ElMenuItem>
      </ElSubMenu>

      <!-- 底部：调优 / 实验对比 -->
      <ElMenuItem v-for="item in bottomItems" :key="item.index" :index="item.index">
        <ElIcon><component :is="item.icon" /></ElIcon>
        <template #title>{{ item.label }}</template>
      </ElMenuItem>
    </ElMenu>
  </aside>
</template>

<style scoped lang="scss">
.sidebar {
  flex: 0 0 auto;
  height: 100vh;
  background-color: var(--bg-card);
  border-right: 1px solid var(--border-color);
  transition: width 0.25s ease-in-out;
  overflow: hidden;
}

.sidebar-menu {
  height: 100%;
  border-right: none;
  padding-top: var(--spacing-sm);

  :deep(.el-menu-item) {
    height: 48px;
    line-height: 48px;
    margin: 2px var(--spacing-sm);
    border-radius: var(--radius);
    font-size: var(--font-size-body);

    &:hover {
      background-color: var(--color-primary-lighter);
      color: var(--color-primary);
    }

    &.is-active {
      background-color: var(--color-primary-lighter);
      font-weight: var(--font-weight-medium);
    }
  }

  :deep(.el-sub-menu) {
    .el-sub-menu__title {
      height: 48px;
      line-height: 48px;
      margin: 2px var(--spacing-sm);
      border-radius: var(--radius);
      font-size: var(--font-size-body);
      font-weight: var(--font-weight-medium);
      color: var(--text-primary);

      &:hover {
        background-color: var(--color-primary-lighter);
      }
    }

    .el-menu-item {
      min-width: auto;
      padding-left: calc(var(--spacing-xl) + 8px) !important;
    }
  }
}
</style>
