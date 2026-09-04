<script setup lang="ts">
// Trace 时间线（spans）
import { ElTimeline, ElTimelineItem, ElCard, ElTag } from 'element-plus'
import type { TraceSpan } from '@/types/trace'

defineProps<{ spans: TraceSpan[] }>()
</script>

<template>
  <ElTimeline>
    <ElTimelineItem
      v-for="span in spans"
      :key="span.id"
      :timestamp="`步骤 ${span.sequence}`"
      placement="top"
    >
      <ElCard shadow="never" class="span-card">
        <div class="span-head">
          <b>{{ span.name }}</b>
          <ElTag size="small">{{ span.kind }}</ElTag>
          <small v-if="span.attributes.turn_id" class="span-turn">
            轮次 {{ span.attributes.turn_id }}
          </small>
        </div>
        <pre class="span-attrs">{{ JSON.stringify(span.attributes, null, 2) }}</pre>
      </ElCard>
    </ElTimelineItem>
  </ElTimeline>
</template>

<style scoped lang="scss">
.span-card {
  :deep(.el-card__body) {
    padding: var(--spacing-md);
  }
}

.span-head {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
  margin-bottom: var(--spacing-sm);

  b {
    color: var(--text-primary);
    font-size: var(--font-size-body);
  }
}

.span-turn {
  color: var(--text-secondary);
  font-size: var(--font-size-small);
}

.span-attrs {
  padding: var(--spacing-sm);
  background-color: var(--gray-100);
  border-radius: var(--radius-small);
  font-size: var(--font-size-small);
  color: var(--text-regular);
  max-height: 240px;
  overflow: auto;
}
</style>
