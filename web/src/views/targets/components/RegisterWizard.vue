<script setup lang="ts">
// 注册向导：基本信息 → 端点/认证 → 能力声明 → 测试连接并注册
// EP 编辑器统一 :model-value + @update:model-value（禁 v-model）
import { computed, reactive, ref } from 'vue'
import {
  ElAlert,
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElOption,
  ElSelect,
  ElStep,
  ElSteps,
  ElTag,
} from 'element-plus'
import { targetsApi } from '@/api/targets'
import type { Capability, ConnectionProbe } from '@/types/target'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'registered'): void
  (e: 'cancel'): void
}>()

const activeStep = ref(0)
const busy = ref(false)
const probing = ref(false)
const probeResult = ref<ConnectionProbe | null>(null)

const form = reactive({
  display_name: '',
  target_type: 'agent' as 'agent' | 'skill',
  description: '',
  endpoint: '',
  credential_ref: '',
  timeout_seconds: 30,
})

const capabilities = ref<Capability[]>([])

const steps = [
  { title: '基本信息', description: '名称与类型' },
  { title: '端点与认证', description: 'HTTP 端点、凭证引用' },
  { title: '能力声明', description: 'Agent 提供的能力' },
  { title: '测试并注册', description: '连通性验证' },
]

const endpointValid = computed(() => /^https?:\/\/\S+$/.test(form.endpoint.trim()))

const stepValid = computed(() => {
  if (activeStep.value === 0) return form.display_name.trim() !== ''
  if (activeStep.value === 1) return endpointValid.value
  return true
})

function nextStep() {
  if (!stepValid.value) {
    ElMessage.warning(
      activeStep.value === 0 ? '请填写展示名称' : '端点必须是 http(s) URL',
    )
    return
  }
  probeResult.value = null
  activeStep.value = Math.min(activeStep.value + 1, steps.length - 1)
}

function prevStep() {
  probeResult.value = null
  activeStep.value = Math.max(activeStep.value - 1, 0)
}

function addCapability() {
  capabilities.value.push({ name: '', kind: 'tool', description: '' })
}

function removeCapability(index: number) {
  capabilities.value.splice(index, 1)
}

const capabilitiesValid = computed(() =>
  capabilities.value.every((item) => item.name.trim() !== ''),
)

async function runProbe() {
  probing.value = true
  probeResult.value = null
  try {
    probeResult.value = await targetsApi.probe({
      endpoint: form.endpoint.trim(),
      credential_ref: form.credential_ref.trim() || null,
      timeout_seconds: 10,
    })
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '测试连接失败')
  } finally {
    probing.value = false
  }
}

const canRegister = computed(
  () => form.display_name.trim() !== '' && endpointValid.value && capabilitiesValid.value,
)

async function submitRegister() {
  if (!canRegister.value) {
    ElMessage.warning('请先补全必填项（名称、端点、能力名）')
    return
  }
  busy.value = true
  try {
    await targetsApi.register({
      display_name: form.display_name.trim(),
      endpoint: form.endpoint.trim(),
      target_type: form.target_type,
      adapter_type: 'http',
      credential_ref: form.credential_ref.trim() || null,
      description: form.description.trim(),
      capabilities: capabilities.value
        .filter((item) => item.name.trim() !== '')
        .map((item) => ({
          name: item.name.trim(),
          kind: item.kind.trim() || 'tool',
          description: item.description.trim(),
        })),
      timeout_seconds: form.timeout_seconds,
    })
    ElMessage.success('评测对象注册成功（已发布 v1）')
    emit('update:visible', false)
    emit('registered')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '注册失败')
  } finally {
    busy.value = false
  }
}

function resetWizard() {
  activeStep.value = 0
  probeResult.value = null
  form.display_name = ''
  form.target_type = 'agent'
  form.description = ''
  form.endpoint = ''
  form.credential_ref = ''
  form.timeout_seconds = 30
  capabilities.value = []
}

function handleClose(open: boolean) {
  emit('update:visible', open)
  if (!open) {
    resetWizard()
    emit('cancel')
  }
}
</script>

<template>
  <ElDialog
    :model-value="props.visible"
    title="注册评测对象"
    width="min(680px, 94vw)"
    @update:model-value="handleClose"
  >
    <ElSteps :active="activeStep" finish-status="success" align-center class="wizard-steps">
      <ElStep
        v-for="step in steps"
        :key="step.title"
        :title="step.title"
        :description="step.description"
      />
    </ElSteps>

    <!-- Step 1: 基本信息 -->
    <ElForm v-show="activeStep === 0" label-position="top" class="wizard-form">
      <ElFormItem label="展示名称" required>
        <ElInput
          :model-value="form.display_name"
          placeholder="例如：订单审批 Agent"
          @update:model-value="(v: string) => (form.display_name = v)"
        />
      </ElFormItem>
      <ElFormItem label="对象类型" required>
        <ElSelect
          :model-value="form.target_type"
          @update:model-value="(v: 'agent' | 'skill') => (form.target_type = v)"
        >
          <ElOption label="Agent（智能体）" value="agent" />
          <ElOption label="Skill（技能）" value="skill" />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="描述">
        <ElInput
          :model-value="form.description"
          type="textarea"
          :rows="3"
          placeholder="对象的用途、负责人等（可选）"
          @update:model-value="(v: string) => (form.description = v)"
        />
      </ElFormItem>
    </ElForm>

    <!-- Step 2: 端点与认证 -->
    <ElForm v-show="activeStep === 1" label-position="top" class="wizard-form">
      <ElFormItem label="HTTP 端点（Invoke 契约）" required>
        <ElInput
          :model-value="form.endpoint"
          placeholder="例如：http://127.0.0.1:8081/invoke"
          @update:model-value="(v: string) => (form.endpoint = v)"
        />
      </ElFormItem>
      <ElFormItem label="凭证引用（credential_ref）">
        <ElInput
          :model-value="form.credential_ref"
          placeholder="环境变量名，例如 AGENTGATE_XXX_API_KEY（可选）"
          @update:model-value="(v: string) => (form.credential_ref = v)"
        />
        <div class="field-hint">
          安全红线：系统只保存环境变量名，密钥明文请在运行环境中配置，请求中一律不传。
        </div>
      </ElFormItem>
      <ElFormItem label="调用超时（秒）">
        <ElInputNumber
          :model-value="form.timeout_seconds"
          :min="1"
          :max="900"
          @update:model-value="(v: number | undefined) => (form.timeout_seconds = v ?? 30)"
        />
      </ElFormItem>
    </ElForm>

    <!-- Step 3: 能力声明 -->
    <div v-show="activeStep === 2" class="wizard-form">
      <ElAlert
        type="info"
        :closable="false"
        show-icon
        title="能力声明描述评测对象能做什么，供后续能力域匹配使用（可选）。"
        class="cap-alert"
      />
      <div v-for="(cap, index) in capabilities" :key="index" class="cap-row">
        <ElInput
          :model-value="cap.name"
          placeholder="能力名，如 loan_approval"
          class="cap-name"
          @update:model-value="(v: string) => (cap.name = v)"
        />
        <ElSelect
          :model-value="cap.kind"
          class="cap-kind"
          @update:model-value="(v: string) => (cap.kind = v)"
        >
          <ElOption label="tool" value="tool" />
          <ElOption label="skill" value="skill" />
          <ElOption label="knowledge" value="knowledge" />
        </ElSelect>
        <ElInput
          :model-value="cap.description"
          placeholder="说明（可选）"
          class="cap-desc"
          @update:model-value="(v: string) => (cap.description = v)"
        />
        <ElButton type="danger" text @click="removeCapability(index)">删除</ElButton>
      </div>
      <ElButton @click="addCapability">+ 添加能力</ElButton>
    </div>

    <!-- Step 4: 测试连接并注册 -->
    <div v-show="activeStep === 3" class="wizard-form probe-step">
      <div class="probe-summary">
        <ElTag>{{ form.display_name || '未命名' }}</ElTag>
        <span class="probe-endpoint">{{ form.endpoint }}</span>
        <ElTag v-if="form.credential_ref" type="warning">
          凭证：{{ form.credential_ref }}
        </ElTag>
      </div>
      <ElButton type="primary" :loading="probing" @click="runProbe">
        测试连接
      </ElButton>
      <ElAlert
        v-if="probeResult && probeResult.ok"
        type="success"
        :closable="false"
        show-icon
        :title="`连接成功（${probeResult.latency_ms ?? '-'}ms）`"
        class="probe-result"
      />
      <ElAlert
        v-if="probeResult && !probeResult.ok"
        type="error"
        :closable="false"
        show-icon
        :title="`连接失败 [${probeResult.error_code ?? 'unknown'}]`"
        :description="probeResult.message ?? ''"
        class="probe-result"
      />
      <div class="field-hint">
        测试连接不是注册的必要条件；但建议在连通后再注册。
      </div>
    </div>

    <template #footer>
      <ElButton v-if="activeStep > 0" @click="prevStep">上一步</ElButton>
      <ElButton
        v-if="activeStep < steps.length - 1"
        type="primary"
        @click="nextStep"
      >
        下一步
      </ElButton>
      <ElButton
        v-if="activeStep === steps.length - 1"
        type="primary"
        :loading="busy"
        :disabled="!canRegister"
        @click="submitRegister"
      >
        确认注册
      </ElButton>
    </template>
  </ElDialog>
</template>

<style scoped lang="scss">
.wizard-steps {
  margin-bottom: var(--spacing-xl, 24px);
}

.wizard-form {
  min-height: 220px;
  padding: 0 var(--spacing-xs, 4px);
}

.field-hint {
  margin-top: var(--spacing-xs, 4px);
  font-size: var(--font-size-small);
  color: var(--text-secondary);
  line-height: 1.5;
}

.cap-alert {
  margin-bottom: var(--spacing-md, 12px);
}

.cap-row {
  display: flex;
  gap: var(--spacing-sm, 8px);
  margin-bottom: var(--spacing-sm, 8px);
  align-items: center;

  .cap-name {
    flex: 2;
  }

  .cap-kind {
    width: 120px;
  }

  .cap-desc {
    flex: 2;
  }
}

.probe-step {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md, 12px);
  align-items: flex-start;
}

.probe-summary {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm, 8px);
  flex-wrap: wrap;

  .probe-endpoint {
    font-family: var(--font-family-mono, monospace);
    font-size: var(--font-size-small);
    color: var(--text-secondary);
    word-break: break-all;
  }
}

.probe-result {
  width: 100%;
}
</style>
