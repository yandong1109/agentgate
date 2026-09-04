<script setup lang="ts">
// 单用例重跑前后对比（对标 App.vue L280-L290）
import { ElTable, ElTableColumn, ElTag, ElButton } from 'element-plus'
import type { RerunComparison } from '@/types/result'
import { comparisonText, comparisonType, outcomeText, asPercent } from '@/utils/format'

defineProps<{ comparison: RerunComparison }>()
const emit = defineEmits<{ openRun: [id: string] }>()
</script>

<template>
  <article class="rerun-comparison" data-testid="rerun-comparison">
    <div class="panel-title">
      <div>
        <h3>单用例重跑对比 · {{ comparison.case_name }}</h3>
        <small class="comparison-sub">
          {{ comparison.before_target_version }} → {{ comparison.after_target_version }}
        </small>
      </div>
      <ElTag :type="comparisonType(comparison.overall)" effect="dark">
        {{ comparisonText[comparison.overall] }}
      </ElTag>
    </div>
    <div class="comparison-summary">
      {{ comparison.counts.improved }} 改善 · {{ comparison.counts.regressed }} 退化 ·
      {{ comparison.counts.unchanged }} 无变化 · {{ comparison.counts.incomparable }} 不可比较
    </div>
    <ElTable :data="comparison.evaluators" size="small">
      <ElTableColumn prop="evaluator_name" label="评估器" min-width="150" />
      <ElTableColumn label="原结果" min-width="180">
        <template #default="scope">
          {{
            (scope.row as RerunComparison['evaluators'][number]).before
              ? `${outcomeText[(scope.row as RerunComparison['evaluators'][number]).before!.outcome]} · ${asPercent((scope.row as RerunComparison['evaluators'][number]).before!.score)}`
              : '—'
          }}
        </template>
      </ElTableColumn>
      <ElTableColumn label="新结果" min-width="180">
        <template #default="scope">
          {{
            (scope.row as RerunComparison['evaluators'][number]).after
              ? `${outcomeText[(scope.row as RerunComparison['evaluators'][number]).after!.outcome]} · ${asPercent((scope.row as RerunComparison['evaluators'][number]).after!.score)}`
              : '—'
          }}
        </template>
      </ElTableColumn>
      <ElTableColumn label="变化" width="110">
        <template #default="scope">
          <ElTag :type="comparisonType((scope.row as RerunComparison['evaluators'][number]).status)" size="small">
            {{ comparisonText[(scope.row as RerunComparison['evaluators'][number]).status] }}
          </ElTag>
        </template>
      </ElTableColumn>
    </ElTable>
    <ElButton link type="primary" @click="emit('openRun', comparison.rerun_run_id)">
      打开重跑完整报告 →
    </ElButton>
  </article>
</template>

<style scoped lang="scss">
.rerun-comparison {
  padding: var(--spacing-xl);
  background-color: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-card);
  box-shadow: var(--elevation-1);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.panel-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);

  h3 {
    font-size: var(--font-size-h4);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
  }
}

.comparison-sub {
  display: block;
  color: var(--text-secondary);
  font-size: var(--font-size-small);
  margin-top: 2px;
}

.comparison-summary {
  font-size: var(--font-size-small);
  color: var(--text-regular);
}
</style>
