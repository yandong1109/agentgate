<script setup lang="ts">
// 用例表（迁移自 web/src/components/dataset/CaseTable.vue）
import { ElButton, ElTag, ElEmpty } from 'element-plus'
import type { EvaluationCase } from '@/types/dataset'

const props = defineProps<{
  items: EvaluationCase[]
  selectedId: string
  editable: boolean
}>()
const emit = defineEmits<{
  select: [item: EvaluationCase]
  add: []
  copy: [item: EvaluationCase]
  remove: [item: EvaluationCase]
  reorder: [ids: string[]]
}>()

const labels: Record<string, string> = {
  positive: '正例',
  negative: '负例',
  boundary: '边界',
  easy: '简单',
  medium: '中等',
  hard: '困难',
}

function move(index: number, offset: number) {
  const ids = props.items.map((item) => item.id)
  const next = index + offset
  if (next < 0 || next >= ids.length) return
  ;[ids[index], ids[next]] = [ids[next], ids[index]]
  emit('reorder', ids)
}
</script>

<template>
  <section class="dataset-column case-list-panel">
    <div class="dataset-panel-heading">
      <div><span class="step">CASES</span><h2>用例</h2></div>
      <ElButton type="primary" size="small" :disabled="!editable" data-testid="add-case" @click="emit('add')">新增用例</ElButton>
    </div>
    <div class="case-list">
      <article
        v-for="(item, index) in items"
        :key="item.id"
        class="case-list-item"
        :class="{ selected: item.id === selectedId }"
        :data-testid="`case-item-${item.id}`"
        @click="emit('select', item)"
      >
        <div class="case-list-main">
          <b>{{ item.name }}</b>
          <span class="case-tags">
            <ElTag size="small" effect="plain">{{ labels[item.category] }}</ElTag>
            <ElTag size="small" effect="plain" type="info">{{ labels[item.difficulty] }}</ElTag>
            <small>{{ item.turns.length }} 轮</small>
          </span>
          <small class="case-notes">{{ item.notes || item.tags.join(' · ') || '暂无备注' }}</small>
        </div>
        <div v-if="editable" class="case-row-actions" @click.stop>
          <ElButton link size="small" :disabled="index === 0" @click="move(index, -1)">↑</ElButton>
          <ElButton link size="small" :disabled="index === items.length - 1" @click="move(index, 1)">↓</ElButton>
          <ElButton link size="small" @click="emit('copy', item)">复制</ElButton>
          <ElButton link size="small" type="danger" @click="emit('remove', item)">删除</ElButton>
        </div>
      </article>
      <ElEmpty v-if="!items.length" description="草稿中还没有用例" :image-size="80" />
    </div>
  </section>
</template>

<style scoped lang="scss">
.case-list-panel {
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

.case-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  overflow-y: auto;
}

.case-list-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
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
}

.case-list-main {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 0;

  b {
    color: var(--text-primary);
    font-size: var(--font-size-body);
  }
}

.case-tags {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  flex-wrap: wrap;

  small {
    color: var(--text-secondary);
    font-size: var(--font-size-small);
  }
}

.case-notes {
  color: var(--text-secondary);
  font-size: var(--font-size-small);
}

.case-row-actions {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex-shrink: 0;
}
</style>
