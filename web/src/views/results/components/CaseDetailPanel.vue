<script setup lang="ts">
// Case 详情折叠面板：只承载"输入侧"信息（每轮输入/初始状态/元信息）
// 期望侧内容（期望技能/必需禁用工具/期望条件）不在本面板展示：
// 它们是各评估器比较时的 expected 来源，已在检查结果的对比面板中出现，避免重复
import { computed, ref } from 'vue'
import { ElTag, ElIcon, ElCollapse, ElCollapseItem } from 'element-plus'
import { ArrowRight } from '@element-plus/icons-vue'
import type { EvaluationCase } from '@/types/dataset'

const props = defineProps<{ evaluationCase: EvaluationCase }>()

const expanded = ref(false)
const activeTurns = computed(() => (expanded.value ? props.evaluationCase.turns.map((t) => t.id) : []))

const categoryText: Record<string, string> = { positive: '正向', negative: '反向', boundary: '边界' }
const difficultyText: Record<string, string> = { easy: '简单', medium: '中等', hard: '困难' }
</script>

<template>
  <div class="case-detail">
    <!-- 头部：切换展开 -->
    <button type="button" class="case-detail-toggle" @click="expanded = !expanded">
      <ElIcon class="toggle-icon" :class="{ 'is-open': expanded }">
        <ArrowRight />
      </ElIcon>
      <span class="toggle-label">用例输入</span>
      <span class="toggle-hint">{{ expanded ? `${evaluationCase.turns.length} 轮对话` : '查看每轮输入' }}</span>
    </button>

    <div v-show="expanded" class="case-detail-body">
      <!-- Case 元信息 -->
      <div class="case-meta">
        <ElTag size="small" effect="plain">{{ categoryText[evaluationCase.category] ?? evaluationCase.category }}</ElTag>
        <ElTag size="small" effect="plain" type="warning">{{ difficultyText[evaluationCase.difficulty] ?? evaluationCase.difficulty }}</ElTag>
        <ElTag v-for="tag in evaluationCase.tags" :key="tag" size="small" effect="plain" type="info">{{ tag }}</ElTag>
        <span v-if="evaluationCase.provenance" class="provenance">
          源自运行 {{ evaluationCase.provenance.source_run_id.slice(0, 8) }} 回归捕获
        </span>
      </div>

      <p v-if="evaluationCase.notes" class="case-notes">{{ evaluationCase.notes }}</p>

      <!-- 初始状态（非空时） -->
      <div v-if="Object.keys(evaluationCase.initial_state).length" class="kv-block">
        <span class="kv-label">初始状态</span>
        <code class="kv-value">{{ JSON.stringify(evaluationCase.initial_state, null, 2) }}</code>
      </div>

      <!-- 每轮输入 -->
      <ElCollapse v-model="activeTurns" class="turns-collapse">
        <ElCollapseItem
          v-for="(turn, i) in evaluationCase.turns"
          :key="turn.id"
          :name="turn.id"
        >
          <template #title>
            <span class="turn-title">
              <b>第 {{ i + 1 }} 轮</b>
              <span class="turn-preview">{{ JSON.stringify(turn.input) }}</span>
            </span>
          </template>

          <div class="turn-body">
            <div class="kv-block">
              <span class="kv-label">输入</span>
              <code class="kv-value">{{ JSON.stringify(turn.input, null, 2) }}</code>
            </div>

            <p v-if="turn.notes" class="turn-notes">{{ turn.notes }}</p>
          </div>
        </ElCollapseItem>
      </ElCollapse>
    </div>
  </div>
</template>

<style scoped lang="scss">
.case-detail {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs, 4px);
  min-width: 0;
  margin-top: var(--spacing-xs, 4px);
}

.case-detail-toggle {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs, 4px);
  padding: 2px var(--spacing-sm, 8px);
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: var(--font-size-small, 12px);
  align-self: flex-start;
  border-radius: var(--radius, 8px);

  &:hover {
    color: var(--color-primary, #07ac8e);
    background-color: var(--color-primary-lighter, #e6f7f3);
  }
}

.toggle-icon {
  font-size: 12px;
  transition: transform 0.2s ease;

  &.is-open {
    transform: rotate(90deg);
  }
}

.toggle-hint {
  color: var(--text-tertiary, #9ca3af);
}

.case-detail-body {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm, 8px);
  padding: var(--spacing-sm, 8px) var(--spacing-md, 12px);
  background-color: var(--bg-muted, #f5f5f7);
  border: 1px solid var(--border-color);
  border-radius: var(--radius, 8px);
}

.case-meta {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs, 4px);
  flex-wrap: wrap;
}

.provenance {
  font-size: var(--font-size-small, 12px);
  color: var(--text-tertiary, #9ca3af);
}

.case-notes {
  margin: 0;
  font-size: var(--font-size-small, 12px);
  color: var(--text-secondary);
}

.kv-block {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.kv-label {
  font-size: var(--font-size-small, 12px);
  font-weight: var(--font-weight-semibold, 600);
  color: var(--text-secondary);
}

.kv-value {
  display: block;
  font-family: var(--font-family-mono, monospace);
  font-size: var(--font-size-small, 12px);
  line-height: 18px;
  color: var(--text-regular, #4b5563);
  background-color: var(--bg-card, #fff);
  border: 1px solid var(--border-color);
  border-radius: var(--radius, 8px);
  padding: 6px 10px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  min-width: 0;
}

.turns-collapse {
  border-top: none;

  :deep(.el-collapse-item__header) {
    font-size: var(--font-size-small, 12px);
    height: 36px;
    line-height: 36px;
    background: transparent;
  }

  :deep(.el-collapse-item__wrap) {
    background: transparent;
  }

  :deep(.el-collapse-item__content) {
    padding-bottom: var(--spacing-sm, 8px);
  }
}

.turn-title {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-sm, 8px);
  min-width: 0;
  overflow: hidden;

  b {
    color: var(--text-primary);
    font-weight: var(--font-weight-semibold, 600);
    flex: 0 0 auto;
  }
}

.turn-preview {
  color: var(--text-tertiary, #9ca3af);
  font-family: var(--font-family-mono, monospace);
  font-size: var(--font-size-small, 12px);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.turn-body {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm, 8px);
  min-width: 0;
}

.turn-notes {
  margin: 0;
  font-size: var(--font-size-small, 12px);
  color: var(--text-secondary);
}
</style>
