<script setup lang="ts">
// Trace 抽屉（对标 App.vue L331-L348）
import { ElDrawer, ElCard } from 'element-plus'
import type { Trace } from '@/types/trace'
import TraceTimeline from './TraceTimeline.vue'
import TurnInspector from './TurnInspector.vue'

defineProps<{
  modelValue: boolean
  trace: Trace | null
  caseName?: string
}>()

const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
</script>

<template>
  <ElDrawer
    :model-value="modelValue"
    title="用例轨迹"
    size="min(520px, 92vw)"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <template v-if="trace">
      <p class="trace-case">{{ caseName }}</p>

      <TurnInspector v-if="trace.turns.length" :turns="trace.turns" />

      <h3 class="trace-section-title">执行轨迹</h3>
      <TraceTimeline :spans="trace.spans" />

      <h3 class="trace-section-title">最终状态</h3>
      <pre class="trace-json">{{ JSON.stringify(trace.final_state, null, 2) }}</pre>

      <h3 class="trace-section-title">最终输出</h3>
      <pre class="trace-json">{{ JSON.stringify(trace.final_output, null, 2) }}</pre>
    </template>
    <ElCard v-else shadow="never" class="trace-empty">暂无轨迹数据</ElCard>
  </ElDrawer>
</template>

<style scoped lang="scss">
.trace-case {
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: var(--spacing-lg);
}

.trace-section-title {
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: var(--spacing-xl) 0 var(--spacing-md);
}

.trace-json {
  padding: var(--spacing-md);
  background-color: var(--gray-100);
  border-radius: var(--radius);
  font-size: var(--font-size-small);
  color: var(--text-regular);
  max-height: 320px;
  overflow: auto;
}

.trace-empty {
  text-align: center;
  color: var(--text-secondary);
}
</style>
