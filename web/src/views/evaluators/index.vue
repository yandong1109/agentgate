<script setup lang="ts">
// 评估器管理页（资产管理组·资产权限分层：内置只读 + 自定义预留）
// 对齐 redesign-plan-zh.md §5.2.2
import { computed, onMounted } from 'vue'
import { ElMessage, ElTable, ElTableColumn, ElTag, ElButton, ElEmpty, ElTooltip } from 'element-plus'
import { useDashboardStore } from '@/stores/modules/dashboard'
import type { EvaluatorOption } from '@/types/evaluator'
import PageContainer from '@/components/PageContainer.vue'

const dashboardStore = useDashboardStore()

// 后端未补 source 字段时默认 builtin（对齐 §5.2.2 后端契约建议）
const evaluators = computed<EvaluatorOption[]>(() =>
  dashboardStore.evaluators.map((e) => ({ ...e, source: e.source ?? 'builtin' })),
)

onMounted(async () => {
  if (!dashboardStore.evaluators.length) {
    try {
      await dashboardStore.refresh()
    } catch (error) {
      ElMessage.error(`无法加载评估器：${error instanceof Error ? error.message : String(error)}`)
    }
  }
})

function isBuiltin(row: EvaluatorOption) {
  return (row.source ?? 'builtin') === 'builtin'
}
</script>

<template>
  <PageContainer>
    <template #heading>
      <div class="region-heading">
        <div class="region-heading-text">
          <span class="step">ASSET · EVALUATORS</span>
          <h2 class="region-title">评估器管理</h2>
          <p class="region-subtitle">
            管理规则、LLM 评审与混合评估器。内置评估器只读，自定义评估器 P2 阶段支持。
          </p>
        </div>
        <ElTooltip content="自定义评估器 P2 阶段支持" placement="bottom">
          <span><ElButton type="primary" disabled>新建评估器</ElButton></span>
        </ElTooltip>
      </div>
    </template>

    <ElTable :data="evaluators" empty-text="暂无评估器" :show-header="true" stripe>
      <ElTableColumn prop="id" label="ID" width="170" />
      <ElTableColumn prop="name" label="名称" width="120" />
      <ElTableColumn prop="kind" label="类型" width="90" />
      <ElTableColumn prop="dimension" label="维度" width="130" />
      <ElTableColumn prop="metric" label="指标" min-width="200" />
      <ElTableColumn label="严重性" width="100">
        <template #default="scope">
          <ElTag
            :type="(scope.row as EvaluatorOption).severity === 'blocking' ? 'danger' : 'info'"
            size="small"
            effect="plain"
          >
            {{ (scope.row as EvaluatorOption).severity === 'blocking' ? '阻断' : '普通' }}
          </ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn label="来源" width="100">
        <template #default="scope">
          <ElTag
            :type="isBuiltin(scope.row as EvaluatorOption) ? 'info' : 'success'"
            size="small"
            effect="light"
          >
            {{ isBuiltin(scope.row as EvaluatorOption) ? '内置' : '自定义' }}
          </ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn label="操作" width="160" fixed="right">
        <template #default="scope">
          <ElButton link type="primary">查看</ElButton>
          <template v-if="!isBuiltin(scope.row as EvaluatorOption)">
            <ElButton link type="warning">编辑</ElButton>
            <ElButton link type="danger">删除</ElButton>
          </template>
        </template>
      </ElTableColumn>
      <template #empty>
        <ElEmpty description="暂无评估器" :image-size="80" />
      </template>
    </ElTable>
  </PageContainer>
</template>

<style scoped lang="scss">
.region-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-lg);
  flex-wrap: wrap;
  width: 100%;
}

.region-heading-text {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.step {
  font-family: var(--font-family-mono);
  font-size: var(--font-size-small);
  letter-spacing: 1px;
  color: var(--color-primary);
  font-weight: var(--font-weight-semibold);
}

.region-title {
  font-size: var(--font-size-h2);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}

.region-subtitle {
  font-size: var(--font-size-body);
  color: var(--text-secondary);
}
</style>
