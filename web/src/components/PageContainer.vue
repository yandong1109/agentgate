<script setup lang="ts">
// PageContainer 页面容器（统一标题与内容区）
import type { Component } from 'vue'

defineProps<{
  title?: string
  description?: string
  icon?: Component
}>()
</script>

<template>
  <section class="page-container">
    <header v-if="title || $slots.heading" class="page-heading">
      <slot name="heading">
        <div class="page-heading-text">
          <h1 v-if="title" class="page-title">{{ title }}</h1>
          <p v-if="description" class="page-description">{{ description }}</p>
        </div>
        <div v-if="$slots.extra" class="page-heading-extra">
          <slot name="extra" />
        </div>
      </slot>
    </header>
    <div class="page-body">
      <slot />
    </div>
  </section>
</template>

<style scoped lang="scss">
.page-container {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
}

.page-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-lg);
  flex-wrap: wrap;
}

.page-heading-text {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.page-title {
  font-size: var(--font-size-h2);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}

.page-description {
  font-size: var(--font-size-body);
  color: var(--text-secondary);
}

.page-body {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
}
</style>
