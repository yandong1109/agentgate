<script setup lang="ts">
// 单用例重跑弹窗（对标 App.vue L295-L304 + L94-L111 submitRerun）
import { computed, ref, watch } from 'vue'
import {
  ElDialog,
  ElForm,
  ElFormItem,
  ElSelect,
  ElOption,
  ElOptionGroup,
  ElAlert,
  ElButton,
  ElMessage,
} from 'element-plus'
import type { Report } from '@/types/result'
import type { Version } from '@/types/target'
import { runsApi } from '@/api/runs'
import { resultsApi } from '@/api/results'
import { useResultStore } from '@/stores/modules/result'
import { agentLabel } from '@/utils/format'

const props = defineProps<{
  modelValue: boolean
  caseId: string
  caseName?: string
  report: Report | null
  versions: Version[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  success: []
}>()

const resultStore = useResultStore()
const rerunVersion = ref('')
const rerunLoading = ref(false)

const groupedVersions = computed<{ label: string; items: Version[] }[]>(() => {
  const groups: Record<string, { label: string; items: Version[] }> = {}
  for (const item of props.versions) {
    const key = item.adapter_type ?? 'python_fn'
    if (!groups[key]) {
      groups[key] = { label: key === 'http' ? 'HTTP Agent' : 'Demo Agent', items: [] }
    }
    groups[key].items.push(item)
  }
  return Object.values(groups)
})

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      rerunVersion.value =
        props.versions.find((item) => item.is_latest)?.id ?? props.versions[0]?.id ?? ''
    }
  },
)

function close() {
  emit('update:modelValue', false)
}

async function submitRerun() {
  if (!props.report || !props.caseId || !rerunVersion.value) return
  rerunLoading.value = true
  try {
    const rerun = await runsApi.rerunCase(props.report.run.id, props.caseId, rerunVersion.value)
    resultStore.setComparison(await resultsApi.comparison(rerun.id))
    emit('success')
    close()
    ElMessage.success('单用例重跑完成，已生成前后对比')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '单用例重跑失败')
  } finally {
    rerunLoading.value = false
  }
}

function onVersionChange(value: string | number | boolean | object | null) {
  rerunVersion.value = String(value)
}
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    title="重新运行单个 Case"
    width="500px"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <template v-if="report">
      <p class="dialog-line"><b>Case：</b>{{ caseName }}</p>
      <p class="dialog-line">
        <b>固定 Dataset：</b>{{ report.run.snapshot.dataset.dataset_name }} v{{
          report.run.snapshot.dataset.version
        }}
      </p>
      <p class="dialog-line"><b>原 Agent 版本：</b>{{ agentLabel(report.run.snapshot.target) }}</p>
      <ElForm label-position="top">
        <ElFormItem label="重跑 Agent 版本">
          <ElSelect
            :model-value="rerunVersion"
            data-testid="rerun-version-select"
            style="width: 100%"
            @update:model-value="onVersionChange"
          >
            <ElOptionGroup
              v-for="group in groupedVersions"
              :key="group.label"
              :label="group.label"
            >
              <ElOption
                v-for="item in group.items"
                :key="item.id"
                :label="`${item.label} · ${item.id}${item.is_latest ? '（最新）' : ''}`"
                :value="item.id"
              />
            </ElOptionGroup>
          </ElSelect>
        </ElFormItem>
      </ElForm>
      <ElAlert
        type="info"
        :closable="false"
        show-icon
        title="Case、评估器、Metric 和 Gate 均复用原 Run 配置。"
      />
    </template>
    <template #footer>
      <ElButton @click="close">取消</ElButton>
      <ElButton
        type="primary"
        :loading="rerunLoading"
        :disabled="!rerunVersion"
        data-testid="submit-rerun"
        @click="submitRerun"
      >开始重跑</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped lang="scss">
.dialog-line {
  margin: 0 0 var(--spacing-sm);
  font-size: var(--font-size-body);
  color: var(--text-regular);

  b {
    color: var(--text-primary);
  }
}
</style>
