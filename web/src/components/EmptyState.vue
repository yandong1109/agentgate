<script setup lang="ts">
// EmptyState 空状态
import { ElEmpty } from 'element-plus'

withDefaults(
  defineProps<{
    description?: string
    imageSize?: number
  }>(),
  {
    description: '暂无数据',
    imageSize: 96,
  },
)
</script>

<template>
  <div class="empty-state">
    <ElEmpty :description="description" :image-size="imageSize">
      <slot />
    </ElEmpty>
  </div>
</template>

<style scoped lang="scss">
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-3xl) var(--spacing-lg);
}
</style>
