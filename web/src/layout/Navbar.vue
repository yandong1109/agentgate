<script setup lang="ts">
// 顶部导航：Logo + 用户菜单（预留）
import { ElIcon } from 'element-plus'
import { Fold, Expand, Sunny, Moon } from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/modules/app'

const appStore = useAppStore()

function toggleSidebar() {
  appStore.toggleSidebar()
}

function toggleTheme() {
  appStore.toggleTheme()
}
</script>

<template>
  <header class="navbar">
    <div class="navbar-left">
      <button class="collapse-btn" :aria-label="appStore.sidebarCollapsed ? '展开侧菜单' : '折叠侧菜单'" @click="toggleSidebar">
        <ElIcon><Fold v-if="!appStore.sidebarCollapsed" /><Expand v-else /></ElIcon>
      </button>
      <div class="brand">
        <span class="brand-mark">AG</span>
        <span class="brand-name">AgentGate</span>
        <span class="brand-suffix">评测平台</span>
      </div>
    </div>
    <div class="navbar-right">
      <button class="theme-btn" aria-label="切换主题" @click="toggleTheme">
        <ElIcon><Sunny v-if="appStore.theme === 'dark'" /><Moon v-else /></ElIcon>
      </button>
      <div class="user-menu">
        <span class="user-avatar">U</span>
        <span class="user-name">本地用户</span>
      </div>
    </div>
  </header>
</template>

<style scoped lang="scss">
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--navbar-height);
  padding: 0 var(--spacing-2xl);
  background-color: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  box-shadow: var(--elevation-1);
  z-index: 100;
}

.navbar-left,
.navbar-right {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.collapse-btn,
.theme-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  background: transparent;
  color: var(--text-regular);
  font-size: 18px;
  transition: all 0.15s ease-in-out;

  &:hover {
    color: var(--color-primary);
    border-color: var(--color-primary);
    background-color: var(--color-primary-lighter);
  }
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius);
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-active));
  color: #fff;
  font-weight: var(--font-weight-bold);
  font-size: 13px;
  letter-spacing: 0.5px;
}

.brand-name {
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}

.brand-suffix {
  font-size: var(--font-size-small);
  color: var(--text-secondary);
  padding-left: var(--spacing-xs);
  border-left: 1px solid var(--border-color);
  margin-left: var(--spacing-xs);
}

.user-menu {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) var(--spacing-md);
  border-radius: var(--radius-full);
  background-color: var(--gray-100);
  cursor: default;
}

.user-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: var(--radius-full);
  background-color: var(--color-primary);
  color: #fff;
  font-size: 12px;
  font-weight: var(--font-weight-semibold);
}

.user-name {
  font-size: var(--font-size-small);
  color: var(--text-regular);
}

@include respond-to(md) {
  .navbar {
    padding: 0 var(--spacing-lg);
  }

  .brand-suffix,
  .user-name {
    display: none;
  }
}
</style>
