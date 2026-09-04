<script setup lang="ts">
// 布局外壳：顶导 + 侧菜单 + 内容区
import { onMounted } from 'vue'
import { useAppStore } from '@/stores/modules/app'
import Navbar from './Navbar.vue'
import Sidebar from './Sidebar.vue'
import AppMain from './AppMain.vue'

const appStore = useAppStore()

onMounted(() => {
  appStore.applyTheme()
})
</script>

<template>
  <div class="app-layout">
    <Sidebar class="app-sidebar" />
    <div class="app-main-section">
      <Navbar class="app-header" />
      <AppMain class="app-content" />
    </div>
  </div>
</template>

<style scoped lang="scss">
.app-layout {
  display: flex;
  height: 100vh;
  width: 100%;
  overflow: hidden;
  background-color: var(--bg-page);
}

.app-main-section {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  height: 100vh;
}

.app-header {
  flex: 0 0 var(--navbar-height);
}

.app-content {
  flex: 1;
  min-height: 0;
}

@include respond-to(md) {
  .app-layout {
    flex-direction: column;
  }

  .app-sidebar {
    position: fixed;
    z-index: 1000;
    height: 100vh;
    transform: translateX(-100%);
    transition: transform 0.25s ease-in-out;

    &.is-mobile-open {
      transform: translateX(0);
    }
  }
}
</style>
