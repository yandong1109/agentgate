<script setup lang="ts">
// Case 结果列表：Tab 分类（全部/失败/通过/不适用）+ Case 折叠（失败默认展开）
import { computed, ref } from 'vue'
import { ElTabs, ElTabPane, ElTag, ElButton, ElEmpty, ElIcon } from 'element-plus'
import { ArrowDown, ArrowRight } from '@element-plus/icons-vue'
import type { Report } from '@/types/result'
import { outcomeText, outcomeType } from '@/utils/format'
import ExpectedActual from './ExpectedActual.vue'
import CaseDetailPanel from './CaseDetailPanel.vue'

const props = defineProps<{
  report: Report
  caseNames: Record<string, string>
}>()

const emit = defineEmits<{
  openTrace: [caseId: string]
  openRerun: [caseId: string]
  openRegression: [caseId: string]
}>()

interface CaseGroup {
  case: Report['run']['snapshot']['dataset']['cases'][number]
  results: Report['results']
}

const caseResults = computed<CaseGroup[]>(
  () =>
    (props.report.run.snapshot.dataset.cases ?? [])
      .filter((item) => props.report.results.some((result) => result.case_id === item.id))
      .map((item) => ({
        case: item,
        results: props.report.results.filter((result) => result.case_id === item.id) ?? [],
      })),
)

function hasFail(group: CaseGroup) {
  return group.results.some((r) => r.outcome === 'fail')
}
function isAllPass(group: CaseGroup) {
  return group.results.length > 0 && group.results.every((r) => r.outcome === 'pass')
}
function isAllNA(group: CaseGroup) {
  return group.results.length > 0 && group.results.every((r) => r.outcome === 'not_applicable')
}

const tabs = computed(() => [
  { name: 'all' as const, label: '全部', count: caseResults.value.length },
  { name: 'fail' as const, label: '失败', count: caseResults.value.filter(hasFail).length },
  { name: 'pass' as const, label: '通过', count: caseResults.value.filter(isAllPass).length },
  { name: 'na' as const, label: '不适用', count: caseResults.value.filter(isAllNA).length },
])

const activeTab = ref<'all' | 'fail' | 'pass' | 'na'>('all')

const filteredCaseResults = computed<CaseGroup[]>(() => {
  switch (activeTab.value) {
    case 'fail':
      return caseResults.value.filter(hasFail)
    case 'pass':
      return caseResults.value.filter(isAllPass)
    case 'na':
      return caseResults.value.filter(isAllNA)
    default:
      return caseResults.value
  }
})

// 折叠状态：默认全部折叠（先看所有用例状态总览），手动展开后记住
const manualToggle = ref<Record<string, boolean>>({})

function isExpanded(group: CaseGroup): boolean {
  return manualToggle.value[group.case.id] === true
}

function toggle(group: CaseGroup) {
  manualToggle.value[group.case.id] = !isExpanded(group)
}
</script>

<template>
  <article class="report-panel">
    <div class="panel-title">
      <h3>检查结果</h3>
    </div>

    <ElTabs v-model="activeTab" class="result-tabs">
      <ElTabPane v-for="tab in tabs" :key="tab.name" :name="tab.name">
        <template #label>
          <span class="tab-label">{{ tab.label }}</span>
          <span class="tab-count">{{ tab.count }}</span>
        </template>

        <ElEmpty v-if="filteredCaseResults.length === 0" description="无符合条件的用例" :image-size="60" />

        <div
          v-for="group in filteredCaseResults"
          :key="group.case.id"
          class="case-result-group"
          :data-testid="`case-result-${group.case.id}`"
        >
          <div class="case-result-title" @click="toggle(group)">
            <span class="case-title-left">
              <ElIcon class="toggle-icon">
                <component :is="isExpanded(group) ? ArrowDown : ArrowRight" />
              </ElIcon>
              <b>{{ group.case.name }}</b>
              <ElTag
                :type="hasFail(group) ? 'danger' : isAllPass(group) ? 'success' : 'info'"
                size="small"
                effect="plain"
              >
                {{ hasFail(group) ? '失败' : isAllPass(group) ? '通过' : '不适用' }}
              </ElTag>
            </span>
            <span class="case-actions" @click.stop>
              <ElButton link type="primary" @click="emit('openTrace', group.case.id)">查看 Trace</ElButton>
              <ElButton
                type="warning"
                plain
                size="small"
                :data-testid="`regression-case-${group.case.id}`"
                @click="emit('openRegression', group.case.id)"
              >加入回归集</ElButton>
              <ElButton
                type="primary"
                plain
                size="small"
                :data-testid="`rerun-case-${group.case.id}`"
                @click="emit('openRerun', group.case.id)"
              >重新运行</ElButton>
            </span>
          </div>

          <div v-show="isExpanded(group)" class="case-results">
            <!-- 用例本体信息（输入/期望技能/工具约束/期望条件），不用跳回测评集 -->
            <CaseDetailPanel :evaluation-case="group.case" />

            <div
              v-for="item in group.results"
              :key="`${item.case_id}-${item.evaluator_id}`"
              class="result-item"
            >
              <div class="result-head">
                <b class="result-evaluator">{{ item.evaluator_name }}</b>
                <ElTag :type="outcomeType(item.outcome)" size="small" class="result-tag">
                  {{ outcomeText[item.outcome] }}
                </ElTag>
              </div>
              <small class="result-reason">{{ item.reason }}</small>
              <ul v-if="item.checks.length" class="check-list">
                <li v-for="check in item.checks" :key="check.id">
                  <div class="check-row">
                    <span class="check-name" :class="{ 'check-fail': check.outcome === 'fail' || check.outcome === 'error' }">
                      {{ check.name }}
                    </span>
                    <ElTag :type="outcomeType(check.outcome)" size="small" effect="plain">
                      {{ outcomeText[check.outcome] }}
                    </ElTag>
                  </div>
                  <small class="check-reason">{{ check.reason }}</small>
                  <ExpectedActual
                    v-if="check.expected !== null || check.actual !== null || check.actual_missing"
                    :expected="check.expected"
                    :actual="check.actual"
                    :actual-missing="check.actual_missing"
                    :outcome="check.outcome"
                    :methods="check.methods"
                    class="check-compare"
                  />
                </li>
              </ul>
            </div>
          </div>
        </div>
      </ElTabPane>
    </ElTabs>
  </article>
</template>

<style scoped lang="scss">
.report-panel {
  padding: var(--spacing-xl);
  background-color: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-card);
  box-shadow: var(--elevation-1);
}

.panel-title {
  margin-bottom: var(--spacing-md);

  h3 {
    font-size: var(--font-size-h4);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
  }
}

.result-tabs {
  :deep(.el-tabs__header) {
    margin-bottom: var(--spacing-md);
  }

  :deep(.el-tabs__item) {
    padding: 0 var(--spacing-md);
  }
}

.tab-label {
  margin-right: var(--spacing-xs);
}

.tab-count {
  font-size: var(--font-size-small);
  padding: 1px 6px;
  border-radius: var(--radius-full);
  background-color: var(--bg-muted, var(--color-primary-lighter));
  color: var(--text-secondary);
}

.case-result-group {
  padding: var(--spacing-md) 0;
  border-top: 1px solid var(--border-color);

  &:first-of-type {
    border-top: none;
    padding-top: 0;
  }
}

.case-result-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
  margin-bottom: var(--spacing-xs);
  cursor: pointer;
  user-select: none;

  &:hover {
    .case-title-left b {
      color: var(--color-primary);
    }
  }
}

.case-title-left {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-sm);
  min-width: 0;

  b {
    color: var(--text-primary);
    font-size: var(--font-size-body);
    font-weight: var(--font-weight-semibold);
    transition: color 0.15s ease;
  }
}

.toggle-icon {
  font-size: 12px;
  color: var(--text-tertiary);
}

.case-actions {
  display: inline-flex;
  gap: var(--spacing-xs);
  flex-wrap: wrap;
}

.case-results {
  padding-top: var(--spacing-xs);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.result-item {
  padding: var(--spacing-sm) 0;
  padding-left: var(--spacing-lg);
}

.result-head {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
  margin-bottom: 2px;
}

.result-evaluator {
  color: var(--text-primary);
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-semibold);
}

.result-tag {
  flex: 0 0 auto;
}

.result-reason {
  display: block;
  color: var(--text-secondary);
  font-size: var(--font-size-small);
  margin-bottom: var(--spacing-xs);
  word-break: break-word;
}

.check-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  margin-bottom: var(--spacing-xs);
  list-style: none;
  margin-left: 0;
  padding-left: var(--spacing-md);

  li {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: var(--font-size-small);
    color: var(--text-regular);
    padding: var(--spacing-xs) 0;
  }
}

.check-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
}

.check-name {
  font-weight: var(--font-weight-medium);
  color: var(--text-regular);

  &.check-fail {
    color: var(--color-danger, #ef4444);
    font-weight: var(--font-weight-semibold);
  }
}

.check-reason {
  color: var(--text-secondary);
  word-break: break-word;
}

.check-compare {
  margin-top: var(--spacing-xs);
}
</style>
