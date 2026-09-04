<script setup lang="ts">
// 轮次检视器（turns）
import { ElCard } from 'element-plus'
import type { TraceTurn } from '@/types/trace'

defineProps<{ turns: TraceTurn[] }>()
</script>

<template>
  <div class="turn-inspector">
    <h3 class="turn-title">各轮输入与输出</h3>
    <ElCard v-for="(turn, index) in turns" :key="turn.turn_id" shadow="never" class="turn-card">
      <b class="turn-head">第 {{ index + 1 }} 轮 · {{ turn.turn_id }}</b>
      <small class="turn-label">输入</small>
      <pre class="turn-json">{{ JSON.stringify(turn.input, null, 2) }}</pre>
      <small class="turn-label">输出</small>
      <pre class="turn-json">{{ JSON.stringify(turn.output, null, 2) }}</pre>
      <small class="turn-label">轮次结束状态</small>
      <pre class="turn-json">{{ JSON.stringify(turn.state, null, 2) }}</pre>
    </ElCard>
  </div>
</template>

<style scoped lang="scss">
.turn-title {
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: var(--spacing-md);
}

.turn-card {
  margin-bottom: var(--spacing-md);

  :deep(.el-card__body) {
    padding: var(--spacing-md);
  }
}

.turn-head {
  display: block;
  color: var(--text-primary);
  font-size: var(--font-size-body);
  margin-bottom: var(--spacing-sm);
}

.turn-label {
  display: block;
  color: var(--text-secondary);
  font-size: var(--font-size-small);
  margin: var(--spacing-sm) 0 var(--spacing-xs);
}

.turn-json {
  padding: var(--spacing-sm);
  background-color: var(--gray-100);
  border-radius: var(--radius-small);
  font-size: var(--font-size-small);
  color: var(--text-regular);
  max-height: 200px;
  overflow: auto;
}
</style>
