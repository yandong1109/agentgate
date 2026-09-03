<script setup lang="ts">
// 版本历史抽屉：版本列表 + 发布新版本 + 按版本测试连接
import { computed, reactive, ref, watch } from 'vue'
import {
  ElAlert,
  ElButton,
  ElDrawer,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus'
import { targetsApi } from '@/api/targets'
import type {
  ConnectionProbe,
  TargetDetail,
  TargetVersionInfo,
} from '@/types/target'

const props = defineProps<{
  visible: boolean
  targetId: string | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'updated'): void
}>()

const loading = ref(false)
const detail = ref<TargetDetail | null>(null)
const probingVersion = ref<number | null>(null)
const probeResults = reactive<Record<number, ConnectionProbe>>({})

const publishBusy = ref(false)
const publishForm = reactive({
  endpoint: '',
  credential_ref: '',
  timeout_seconds: undefined as number | undefined,
})

const versions = computed(() => detail.value?.versions ?? [])

const latest = computed(
  () => versions.value.find((item) => item.is_latest) ?? null,
)

async function loadDetail() {
  if (!props.targetId) return
  loading.value = true
  try {
    detail.value = await targetsApi.detail(props.targetId)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载版本失败')
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.visible, props.targetId],
  ([visible]) => {
    if (visible) {
      Object.keys(probeResults).forEach((key) => delete probeResults[Number(key)])
      publishForm.endpoint = ''
      publishForm.credential_ref = ''
      publishForm.timeout_seconds = undefined
      loadDetail()
    }
  },
  { immediate: true },
)

async function probeVersion(version: TargetVersionInfo) {
  probingVersion.value = version.version
  try {
    probeResults[version.version] = await targetsApi.probeTarget(
      props.targetId!,
      { version: version.version },
    )
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '测试连接失败')
  } finally {
    probingVersion.value = null
  }
}

const publishPayloadValid = computed(() => {
  if (!publishForm.endpoint.trim()) return true // 不填则继承上一版本
  return /^https?:\/\/\S+$/.test(publishForm.endpoint.trim())
})

async function submitPublish() {
  if (!props.targetId) return
  if (!publishPayloadValid.value) {
    ElMessage.warning('端点必须是 http(s) URL')
    return
  }
  publishBusy.value = true
  try {
    const published = await targetsApi.publishVersion(props.targetId, {
      endpoint: publishForm.endpoint.trim() || undefined,
      credential_ref: publishForm.credential_ref.trim() || undefined,
      timeout_seconds: publishForm.timeout_seconds,
    })
    ElMessage.success(`已发布 v${published.version}（内容哈希已固化）`)
    publishForm.endpoint = ''
    publishForm.credential_ref = ''
    publishForm.timeout_seconds = undefined
    await loadDetail()
    emit('updated')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '发布失败')
  } finally {
    publishBusy.value = false
  }
}

function shortSha(sha: string) {
  return sha ? sha.slice(0, 12) : '-'
}

function formatDate(value: string | undefined) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

function handleVisible(open: boolean) {
  emit('update:visible', open)
}
</script>

<template>
  <ElDrawer
    :model-value="props.visible"
    title="版本管理"
    size="min(720px, 96vw)"
    @update:model-value="handleVisible"
  >
    <div v-if="detail" class="drawer-body" v-loading="loading">
      <div class="target-meta">
        <h3 class="target-name">{{ detail.display_name }}</h3>
        <div class="target-sub">
          <ElTag size="small">{{ detail.external_target_id }}</ElTag>
          <ElTag size="small" type="info">{{ detail.adapter_type }}</ElTag>
          <ElTag size="small" type="warning">
            {{ detail.target_type === 'agent' ? 'Agent' : 'Skill' }}
          </ElTag>
        </div>
        <p v-if="detail.description" class="target-desc">{{ detail.description }}</p>
      </div>

      <h4 class="section-title">已发布版本（不可变）</h4>
      <ElTable :data="versions" stripe size="small">
        <ElTableColumn label="版本" width="90">
          <template #default="{ row }">
            <ElTag v-if="row.is_latest" type="success" size="small">
              v{{ row.version }} · 最新
            </ElTag>
            <span v-else>v{{ row.version }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="endpoint" label="端点" min-width="200" show-overflow-tooltip />
        <ElTableColumn label="凭证引用" width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.credential_ref" class="mono">{{ row.credential_ref }}</span>
            <span v-else class="muted">未配置</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="内容哈希" width="130">
          <template #default="{ row }">
            <span class="mono" :title="row.content_sha256">
              {{ shortSha(row.content_sha256) }}
            </span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="发布时间" width="150">
          <template #default="{ row }">{{ formatDate(row.published_at) }}</template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <ElButton
              size="small"
              :loading="probingVersion === row.version"
              @click="probeVersion(row as TargetVersionInfo)"
            >
              测试
            </ElButton>
          </template>
        </ElTableColumn>
      </ElTable>

      <template v-for="version in versions" :key="version.version">
        <ElAlert
          v-if="probeResults[version.version]"
          :type="probeResults[version.version].ok ? 'success' : 'error'"
          :closable="false"
          show-icon
          class="probe-alert"
          :title="
            probeResults[version.version].ok
              ? `v${version.version} 连接成功（${probeResults[version.version].latency_ms ?? '-'}ms）`
              : `v${version.version} 连接失败 [${probeResults[version.version].error_code ?? 'unknown'}]`
          "
          :description="probeResults[version.version].message ?? ''"
        />
      </template>

      <h4 class="section-title">发布新版本</h4>
      <ElAlert
        type="info"
        :closable="false"
        show-icon
        class="publish-hint"
        title="留空的字段继承最新版本；发布后内容（含内容哈希）不可再修改。"
      />
      <ElForm label-position="top" class="publish-form">
        <ElFormItem label="新端点（留空继承当前）">
          <ElInput
            :model-value="publishForm.endpoint"
            :placeholder="latest ? latest.endpoint : 'http://...'"
            @update:model-value="(v: string) => (publishForm.endpoint = v)"
          />
        </ElFormItem>
        <ElFormItem label="凭证引用（留空继承当前）">
          <ElInput
            :model-value="publishForm.credential_ref"
            :placeholder="latest?.credential_ref ?? '环境变量名（可选）'"
            @update:model-value="(v: string) => (publishForm.credential_ref = v)"
          />
        </ElFormItem>
        <ElFormItem label="调用超时（秒，留空继承当前）">
          <ElInputNumber
            :model-value="publishForm.timeout_seconds"
            :min="1"
            :max="900"
            :placeholder="latest ? String(latest.invocation_config.timeout_seconds ?? 30) : '30'"
            @update:model-value="(v: number | undefined) => (publishForm.timeout_seconds = v)"
          />
        </ElFormItem>
        <ElButton type="primary" :loading="publishBusy" @click="submitPublish">
          发布版本
        </ElButton>
      </ElForm>
    </div>
  </ElDrawer>
</template>

<style scoped lang="scss">
.drawer-body {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md, 12px);
}

.target-meta {
  .target-name {
    margin: 0 0 var(--spacing-sm, 8px);
    font-size: 18px;
  }

  .target-sub {
    display: flex;
    gap: var(--spacing-xs, 4px);
  }

  .target-desc {
    margin: var(--spacing-sm, 8px) 0 0;
    color: var(--text-secondary);
    font-size: var(--font-size-small);
  }
}

.section-title {
  margin: var(--spacing-lg, 16px) 0 var(--spacing-xs, 4px);
  font-size: 15px;
}

.mono {
  font-family: var(--font-family-mono, monospace);
  font-size: var(--font-size-small);
}

.muted {
  color: var(--text-secondary);
}

.probe-alert {
  margin-top: var(--spacing-sm, 8px);
}

.publish-hint {
  margin-bottom: var(--spacing-md, 12px);
}
</style>
