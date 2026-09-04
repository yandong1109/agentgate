<script setup lang="ts">
// 内容区：内边距 24px，max-width 1600px 居中
</script>

<template>
  <section class="app-main">
    <div class="app-main-inner">
      <RouterView v-slot="{ Component, route }">
        <Transition name="fade-transform" mode="out-in">
          <component :is="Component" :key="route.path" />
        </Transition>
      </RouterView>
    </div>
  </section>
</template>

<style scoped lang="scss">
.app-main {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.app-main-inner {
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: var(--content-padding);
}

.fade-transform-enter-active,
.fade-transform-leave-active {
  transition: all 0.25s ease-in-out;
}

.fade-transform-enter-from {
  opacity: 0;
  transform: translateX(12px);
}

.fade-transform-leave-to {
  opacity: 0;
  transform: translateX(-12px);
}

@include respond-to(md) {
  .app-main-inner {
    padding: var(--spacing-lg);
  }
}
</style>
