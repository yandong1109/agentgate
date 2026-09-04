<script setup lang="ts">
// ComingSoon 占位组件（未实现模块统一展示）
import { ElIcon } from 'element-plus'
import type { Component } from 'vue'

withDefaults(
  defineProps<{
    icon?: Component
    title?: string
    description?: string
    phase?: string
  }>(),
  {
    icon: undefined,
    title: '即将上线',
    description: '该模块正在规划中，敬请期待。',
    phase: 'P2',
  },
)
</script>

<template>
  <section class="coming-soon">
    <div class="coming-soon-card">
      <div v-if="icon" class="coming-soon-icon">
        <ElIcon :size="48"><component :is="icon" /></ElIcon>
      </div>
      <div v-else class="coming-soon-emoji">🚧</div>
      <h2 class="coming-soon-title">{{ title }}</h2>
      <p class="coming-soon-desc">{{ description }}</p>
      <span class="coming-soon-phase">预计阶段 · {{ phase }}</span>
    </div>
  </section>
</template>

<style scoped lang="scss">
.coming-soon {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  padding: var(--spacing-3xl);
}

.coming-soon-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: var(--spacing-4xl);
  background-color: var(--bg-card);
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-card);
  max-width: 520px;
  width: 100%;
}

.coming-soon-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 88px;
  height: 88px;
  margin-bottom: var(--spacing-xl);
  border-radius: var(--radius-full);
  background-color: var(--color-primary-lighter);
  color: var(--color-primary);
}

.coming-soon-emoji {
  font-size: 56px;
  margin-bottom: var(--spacing-xl);
}

.coming-soon-title {
  font-size: var(--font-size-h3);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: var(--spacing-sm);
}

.coming-soon-desc {
  font-size: var(--font-size-body);
  color: var(--text-secondary);
  line-height: var(--line-height-base);
  margin-bottom: var(--spacing-lg);
}

.coming-soon-phase {
  display: inline-block;
  padding: var(--spacing-xs) var(--spacing-lg);
  border-radius: var(--radius-full);
  background-color: var(--gray-100);
  color: var(--text-secondary);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
}
</style>
