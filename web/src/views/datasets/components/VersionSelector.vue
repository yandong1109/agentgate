<script setup lang="ts">
// 版本选择器（迁移自 web/src/components/dataset/VersionSelector.vue）
import { ElButton } from 'element-plus'
import type { DatasetVersion } from '@/types/dataset'

defineProps<{
  versions: DatasetVersion[]
  activeId: string
  busy?: boolean
}>()
const emit = defineEmits<{
  select: [version: DatasetVersion]
  createDraft: [base: number | null]
  publish: []
  discard: []
  export: [version: number]
  exportExcel: [version: number]
}>()
</script>

<template>
  <div class="version-toolbar">
    <div class="version-tabs" aria-label="测评集版本">
      <button
        v-for="item in versions"
        :key="item.id"
        :class="{ active: item.id === activeId }"
        :data-testid="`version-${item.status}-${item.version ?? 'draft'}`"
        @click="emit('select', item)"
      >
        <span>{{ item.status === 'draft' ? '当前草稿' : `v${item.version}` }}</span>
        <small>{{
          item.status === 'draft' ? `基于 v${item.based_on_version ?? '空白'}` : '已发布'
        }}</small>
      </button>
    </div>
    <div class="version-actions">
      <template v-if="versions.find((item) => item.id === activeId)?.status === 'draft'">
        <ElButton size="small" @click="emit('discard')">放弃草稿</ElButton>
        <ElButton
          type="success"
          size="small"
          :loading="busy"
          data-testid="publish-draft"
          @click="emit('publish')"
          >验证并发布</ElButton
        >
      </template>
      <template v-else>
        <ElButton
          size="small"
          :disabled="versions.some((item) => item.status === 'draft')"
          data-testid="create-draft"
          @click="
            emit('createDraft', versions.find((item) => item.id === activeId)?.version ?? null)
          "
          >新建版本</ElButton
        >
        <ElButton
          v-if="versions.find((item) => item.id === activeId)?.version"
          size="small"
          @click="emit('export', versions.find((item) => item.id === activeId)!.version!)"
          >导出 JSON</ElButton
        >
        <ElButton
          v-if="versions.find((item) => item.id === activeId)?.version"
          size="small"
          data-testid="export-excel"
          @click="emit('exportExcel', versions.find((item) => item.id === activeId)!.version!)"
          >导出 Excel</ElButton
        >
      </template>
    </div>
  </div>
</template>

<style scoped lang="scss">
.version-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
  padding: var(--spacing-sm) var(--spacing-lg);
  background-color: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-card);
  box-shadow: var(--elevation-1);
  flex-wrap: wrap;
}

.version-tabs {
  display: flex;
  gap: var(--spacing-xs);
  flex-wrap: wrap;

  button {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    padding: var(--spacing-xs) var(--spacing-md);
    border: 1px solid var(--border-color);
    border-radius: var(--radius);
    background: transparent;
    cursor: pointer;
    transition: all 0.15s ease-in-out;

    span {
      color: var(--text-primary);
      font-size: var(--font-size-small);
      font-weight: var(--font-weight-medium);
    }

    small {
      color: var(--text-secondary);
      font-size: 10px;
    }

    &.active {
      border-color: var(--color-primary);
      background-color: var(--color-primary-lighter);

      span {
        color: var(--color-primary-active);
      }
    }
  }
}

.version-actions {
  display: flex;
  gap: var(--spacing-xs);
  flex-wrap: wrap;
}
</style>
