<script setup lang="ts">
// 测评集列表（迁移自 web/src/components/dataset/DatasetList.vue）
// §6.1：el-input 用 :model-value + @update:modelValue
import { computed, ref } from 'vue'
import {
  ElInput,
  ElButton,
  ElDropdown,
  ElDropdownMenu,
  ElDropdownItem,
  ElTag,
  ElEmpty,
} from 'element-plus'
import type { DatasetSummary } from '@/types/dataset'

const props = defineProps<{
  items: DatasetSummary[]
  selectedId: string
  loading?: boolean
}>()
const emit = defineEmits<{
  select: [id: string]
  create: []
  copy: [item: DatasetSummary]
  archive: [item: DatasetSummary]
  import: []
  importExcel: []
  downloadExcelTemplate: []
}>()

const query = ref('')
const filtered = computed(() => {
  const value = query.value.trim().toLowerCase()
  if (!value) return props.items
  return props.items.filter(
    (item) =>
      item.name.toLowerCase().includes(value) || item.description.toLowerCase().includes(value),
  )
})
</script>

<template>
  <aside class="dataset-column dataset-list-panel">
    <div class="dataset-panel-heading">
      <div>
        <span class="step">DATASETS</span>
        <h2>测评集</h2>
      </div>
      <ElButton type="primary" size="small" data-testid="create-dataset" @click="emit('create')"
        >新建</ElButton
      >
    </div>
    <ElInput
      :model-value="query"
      clearable
      placeholder="搜索测评集"
      aria-label="搜索测评集"
      @update:model-value="(v: string) => (query = v)"
    />
    <div v-loading="loading" class="dataset-list">
      <button
        v-for="item in filtered"
        :key="item.id"
        class="dataset-list-item"
        :class="{ selected: item.id === selectedId }"
        :data-testid="`dataset-item-${item.id}`"
        @click="emit('select', item.id)"
      >
        <span class="dataset-item-main">
          <b>{{ item.name }}</b>
          <small>{{ item.description || '暂无描述' }}</small>
        </span>
        <span class="dataset-badges">
          <ElTag v-if="item.purpose === 'regression'" size="small" type="danger" effect="plain"
            >回归集</ElTag
          >
          <ElTag size="small" effect="plain">v{{ item.version ?? '—' }}</ElTag>
          <ElTag v-if="item.has_draft" size="small" type="warning">草稿</ElTag>
          <small>{{ item.case_count }} 用例</small>
        </span>
      </button>
      <ElEmpty v-if="!filtered.length" description="暂无测评集" :image-size="72" />
    </div>
    <div class="dataset-list-actions">
      <ElButton size="small" data-testid="import-json" @click="emit('import')">导入 JSON</ElButton>
      <ElButton size="small" data-testid="import-excel" @click="emit('importExcel')"
        >导入 Excel</ElButton
      >
      <ElButton
        size="small"
        data-testid="download-excel-template"
        @click="emit('downloadExcelTemplate')"
        >下载模板</ElButton
      >
      <ElDropdown v-if="items.find((item) => item.id === selectedId)" trigger="click">
        <ElButton size="small">更多</ElButton>
        <template #dropdown>
          <ElDropdownMenu>
            <ElDropdownItem
              @click="
                emit(
                  'copy',
                  items.find((item) => item.id === selectedId)!,
                )
              "
              >复制测评集</ElDropdownItem
            >
            <ElDropdownItem
              divided
              @click="
                emit(
                  'archive',
                  items.find((item) => item.id === selectedId)!,
                )
              "
              >归档测评集</ElDropdownItem
            >
          </ElDropdownMenu>
        </template>
      </ElDropdown>
    </div>
  </aside>
</template>

<style scoped lang="scss">
.dataset-list-panel {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  padding: var(--spacing-lg) !important;
  min-height: 480px;
}

.dataset-panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm);

  h2 {
    font-size: var(--font-size-h4);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
    margin: 0;
  }

  .step {
    display: block;
    font-family: var(--font-family-mono);
    font-size: 10px;
    color: var(--color-primary);
    letter-spacing: 1px;
  }
}

.dataset-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  overflow-y: auto;
}

.dataset-list-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: var(--spacing-sm) var(--spacing-md);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: all 0.15s ease-in-out;

  &:hover {
    border-color: var(--color-primary);
    background-color: var(--color-primary-lighter);
  }

  &.selected {
    border-color: var(--color-primary);
    background-color: var(--color-primary-lighter);
  }

  b {
    color: var(--text-primary);
    font-size: var(--font-size-body);
  }

  small {
    color: var(--text-secondary);
    font-size: var(--font-size-small);
  }
}

.dataset-item-main {
  display: flex;
  flex-direction: column;
}

.dataset-badges {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  flex-wrap: wrap;

  small {
    color: var(--text-secondary);
  }
}

.dataset-list-actions {
  display: flex;
  gap: var(--spacing-xs);
}
</style>
