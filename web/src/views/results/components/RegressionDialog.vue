<script setup lang="ts">
// 加入回归集弹窗（对标 App.vue L306-L329 + L112-L144 submitRegression）
import { computed, ref, watch } from 'vue'
import {
  ElDialog,
  ElForm,
  ElFormItem,
  ElSelect,
  ElOption,
  ElInput,
  ElRadioGroup,
  ElRadioButton,
  ElAlert,
  ElButton,
  ElMessage,
} from 'element-plus'
import type { Report } from '@/types/result'
import type { DatasetSummary } from '@/types/dataset'
import { datasetsApi } from '@/api/datasets'

const props = defineProps<{
  modelValue: boolean
  caseId: string
  caseName?: string
  report: Report | null
  datasets: DatasetSummary[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  success: []
}>()

const mode = ref<'existing' | 'new'>('new')
const datasetId = ref('')
const name = ref('')
const description = ref('')
const reason = ref('')
const loading = ref(false)

const regressionDatasets = computed(() => props.datasets.filter((item) => item.purpose === 'regression'))

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      mode.value = regressionDatasets.value.length ? 'existing' : 'new'
      datasetId.value = regressionDatasets.value[0]?.id ?? ''
      name.value = ''
      description.value = ''
      reason.value = ''
    }
  },
)

function close() {
  emit('update:modelValue', false)
}

function onModeChange(value: string | number | boolean | undefined) {
  mode.value = value as 'existing' | 'new'
}
function onDatasetChange(value: string | number | boolean | object | null) {
  datasetId.value = String(value)
}

async function submitRegression() {
  if (!props.report || !props.caseId) return
  if (mode.value === 'existing' && !datasetId.value) return ElMessage.warning('请选择回归集')
  if (mode.value === 'new' && !name.value.trim()) return ElMessage.warning('请输入回归集名称')
  loading.value = true
  try {
    const payload =
      mode.value === 'existing'
        ? { regression_dataset_id: datasetId.value, reason: reason.value }
        : {
            new_dataset_name: name.value,
            new_dataset_description: description.value,
            reason: reason.value,
          }
    const result = await datasetsApi.addCaseToRegressionDataset(
      props.report.run.id,
      props.caseId,
      payload,
    )
    emit('success')
    close()
    ElMessage.success(`已加入回归集“${result.dataset.name}”草稿`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加入回归集失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    title="加入回归集"
    width="540px"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <template v-if="report">
      <p class="dialog-line"><b>Case：</b>{{ caseName }}</p>
      <p class="dialog-line">
        <b>来源：</b>{{ report.run.snapshot.dataset.dataset_name }} v{{
          report.run.snapshot.dataset.version
        }} · Run {{ report.run.id }}
      </p>
      <ElRadioGroup :model-value="mode" data-testid="regression-mode" @update:model-value="onModeChange">
        <ElRadioButton value="existing" :disabled="!regressionDatasets.length">已有回归集</ElRadioButton>
        <ElRadioButton value="new">新建回归集</ElRadioButton>
      </ElRadioGroup>
      <ElForm label-position="top" class="regression-form">
        <ElFormItem v-if="mode === 'existing'" label="目标回归集">
          <ElSelect
            :model-value="datasetId"
            data-testid="regression-dataset-select"
            style="width: 100%"
            @update:model-value="onDatasetChange"
          >
            <ElOption v-for="item in regressionDatasets" :key="item.id" :label="item.name" :value="item.id" />
          </ElSelect>
        </ElFormItem>
        <template v-else>
          <ElFormItem label="回归集名称">
            <ElInput :model-value="name" data-testid="regression-name" @update:model-value="(v: string) => (name = v)" />
          </ElFormItem>
          <ElFormItem label="说明">
            <ElInput
              :model-value="description"
              type="textarea"
              :rows="2"
              @update:model-value="(v: string) => (description = v)"
            />
          </ElFormItem>
        </template>
        <ElFormItem label="加入原因（可选）">
          <ElInput
            :model-value="reason"
            type="textarea"
            :rows="2"
            data-testid="regression-reason"
            @update:model-value="(v: string) => (reason = v)"
          />
        </ElFormItem>
      </ElForm>
      <ElAlert
        type="info"
        :closable="false"
        title="Case 将从本次 Run 快照复制到回归集草稿，发布后可按普通测评集运行。"
      />
    </template>
    <template #footer>
      <ElButton @click="close">取消</ElButton>
      <ElButton
        type="primary"
        :loading="loading"
        data-testid="submit-regression"
        @click="submitRegression"
      >确认加入</ElButton>
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

.regression-form {
  margin-top: var(--spacing-md);
}
</style>
