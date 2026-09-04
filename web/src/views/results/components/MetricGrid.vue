<script setup lang="ts">
// 指标卡网格：维度色彩条 + 失败标红 + score 加大
import { computed } from 'vue'
import { ElProgress } from 'element-plus'
import type { Report, Metric } from '@/types/result'
import { asPercent } from '@/utils/format'

const props = defineProps<{ report: Report }>()

const metrics = computed<Metric[]>(() => props.report.metrics)

function isFailed(metric: Metric): boolean {
  return metric.failed > 0 || metric.errors > 0
}
</script>

<template>
  <div class="metric-grid" aria-label="评估指标">
    <article
      v-for="metric in metrics"
      :key="`${metric.level}-${metric.key}`"
      class="metric-card"
      :class="{ 'is-failed': isFailed(metric) }"
      :data-testid="`metric-${metric.level}-${metric.key}`"
    >
      <span class="metric-label">{{ metric.label }} · {{ metric.level }}</span>
      <strong class="metric-score">{{ asPercent(metric.score) }}</strong>
      <ElProgress
        :percentage="Math.round((metric.score ?? 0) * 100)"
        :show-text="false"
        :stroke-width="8"
        :color="isFailed(metric) ? '#ef4444' : '#07ac8e'"
      />
      <small class="metric-detail">
        {{ metric.passed }} 通过 · {{ metric.failed }} 失败 · {{ metric.not_applicable }} 不适用
        <span v-if="metric.errors"> · {{ metric.errors }} 错误</span>
      </small>
    </article>
  </div>
</template>

<style scoped lang="scss">
.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--spacing-lg);
}

.metric-card {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  padding: var(--spacing-lg);
  background-color: var(--bg-card);
  border: 1px solid var(--border-color);
  border-left: 3px solid var(--color-primary);
  border-radius: var(--radius-card);
  box-shadow: var(--elevation-1);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;

  &:hover {
    box-shadow: var(--elevation-2);
  }

  &.is-failed {
    border-left-color: var(--color-danger);

    .metric-score {
      color: var(--color-danger);
    }
  }
}

.metric-label {
  font-size: var(--font-size-small);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.metric-score {
  font-size: var(--font-size-h2);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  font-family: var(--font-family-mono);
  line-height: 1.2;
}

.metric-detail {
  font-size: var(--font-size-small);
  color: var(--text-secondary);
}
</style>
