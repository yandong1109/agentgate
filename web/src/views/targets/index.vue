<script setup lang="ts">
// 评测对象管理：注册、配置、版本化 Agent 目标（端点、认证、能力声明）
import { computed, onMounted, ref } from 'vue'
import {
  ElButton,
  ElDialog,
  ElEmpty,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElSelect,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus'
import { targetsApi } from '@/api/targets'
import type { ConnectionProbe, TargetListItem } from '@/types/target'
import PageContainer from '@/components/PageContainer.vue'
import RegisterWizard from './components/RegisterWizard.vue'
import VersionDrawer from './components/VersionDrawer.vue'

const targets = ref<TargetListItem[]>([])
const loading = ref(false)
const keyword = ref('')
const typeFilter = ref<'' | 'agent' | 'skill'>('')

const wizardVisible = ref(false)
const drawerVisible = ref(false)
const drawerTargetId = ref<string | null>(null)

const probingId = ref<string | null>(null)
const probeDialogVisible = ref(false)
const probeTarget = ref<TargetListItem | null>(null)
const probeResult = ref<ConnectionProbe | null>(null)

const stats = computed(() => ({
  total: targets.value.length,
  agents: targets.value.filter((item) => item.target_type === 'agent').length,
  skills: targets.value.filter((item) => item.target_type === 'skill').length,
  versionTotal: targets.value.reduce((sum, item) => sum + item.version_count, 0),
}))

const filtered = computed(() => {
  const word = keyword.value.trim().toLowerCase()
  return targets.value.filter((item) => {
    if (typeFilter.value && item.target_type !== typeFilter.value) return false
    if (!word) return true
    return (
      item.display_name.toLowerCase().includes(word) ||
      item.external_target_id.toLowerCase().includes(word) ||
      (item.latest_version?.endpoint ?? '').toLowerCase().includes(word)
    )
  })
})

async function loadTargets() {
  loading.value = true
  try {
    targets.value = await targetsApi.list()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载评测对象失败')
  } finally {
    loading.value = false
  }
}

function openWizard() {
  wizardVisible.value = true
}

function openVersions(target: TargetListItem) {
  drawerTargetId.value = target.id
  drawerVisible.value = true
}

async function runProbe(target: TargetListItem) {
  probingId.value = target.id
  probeTarget.value = target
  probeResult.value = null
  probeDialogVisible.value = true
  try {
    probeResult.value = await targetsApi.probeTarget(target.id)
  } catch (error) {
    probeResult.value = {
      ok: false,
      error_code: 'request_failed',
      message: error instanceof Error ? error.message : '请求失败',
    }
  } finally {
    probingId.value = null
  }
}

async function handleDelete(target: TargetListItem) {
  try {
    await ElMessageBox.confirm(
      `确定删除评测对象"${target.display_name}"吗？软删除后可保证历史数据可审计。`,
      '删除评测对象',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await targetsApi.remove(target.id)
    ElMessage.success('已删除')
    await loadTargets()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '删除失败')
  }
}

function formatDate(value: string | undefined) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

function closeProbeDialog() {
  probeDialogVisible.value = false
}

onMounted(loadTargets)
</script>

<template>
  <PageContainer
    title="评测对象"
    description="注册、配置、版本化 Agent 目标（含端点、认证、能力声明等）。"
  >
    <div class="stats-container">
      <div class="stat-card">
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">评测对象</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.agents }}</div>
        <div class="stat-label">Agent</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.skills }}</div>
        <div class="stat-label">Skill</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.versionTotal }}</div>
        <div class="stat-label">已发布版本</div>
      </div>
    </div>

    <div class="action-bar">
      <ElButton type="primary" @click="openWizard">注册评测对象</ElButton>
      <ElButton @click="loadTargets">刷新</ElButton>
      <div class="filters">
        <ElInput
          :model-value="keyword"
          clearable
          placeholder="搜索名称 / ID / 端点"
          class="search-input"
          @update:model-value="(v: string) => (keyword = v)"
        />
        <ElSelect
          :model-value="typeFilter"
          clearable
          placeholder="全部类型"
          class="type-select"
          @update:model-value="(v: '' | 'agent' | 'skill') => (typeFilter = v ?? '')"
        >
          <ElOption label="Agent" value="agent" />
          <ElOption label="Skill" value="skill" />
        </ElSelect>
      </div>
    </div>

    <template v-if="filtered.length || loading">
      <ElTable v-loading="loading" :data="filtered" stripe class="target-table">
        <ElTableColumn label="名称" min-width="180">
          <template #default="{ row }">
            <div class="name-cell">
              <span class="target-name">{{ row.display_name }}</span>
              <span class="target-id mono">{{ row.external_target_id }}</span>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn label="类型" width="90" align="center">
          <template #default="{ row }">
            <ElTag size="small" :type="row.target_type === 'agent' ? 'primary' : 'warning'">
              {{ row.target_type === 'agent' ? 'Agent' : 'Skill' }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="端点（最新版本）" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.latest_version" class="mono endpoint">
              {{ row.latest_version.endpoint }}
            </span>
            <span v-else class="muted">未发布版本</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="认证" width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.latest_version?.credential_ref" class="mono">
              {{ row.latest_version.credential_ref }}
            </span>
            <span v-else class="muted">未配置</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="能力" width="80" align="center">
          <template #default="{ row }">
            <ElTag v-if="row.capabilities.length" size="small" type="info">
              {{ row.capabilities.length }}
            </ElTag>
            <span v-else class="muted">-</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="版本" width="90" align="center">
          <template #default="{ row }">
            <ElTag v-if="row.latest_version" size="small" type="success">
              v{{ row.latest_version.version }}
            </ElTag>
            <span v-else class="muted">0</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="注册时间" width="160">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <ElButton
              size="small"
              :loading="probingId === row.id"
              @click="runProbe(row as TargetListItem)"
            >
              测试连接
            </ElButton>
            <ElButton size="small" type="primary" @click="openVersions(row as TargetListItem)">
              版本管理
            </ElButton>
            <ElButton size="small" type="danger" @click="handleDelete(row as TargetListItem)">
              删除
            </ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </template>
    <ElEmpty v-else description="暂无评测对象，点击右上角「注册评测对象」开始接入">
      <ElButton type="primary" @click="openWizard">注册评测对象</ElButton>
    </ElEmpty>

    <RegisterWizard
      :visible="wizardVisible"
      @update:visible="(v: boolean) => (wizardVisible = v)"
      @registered="loadTargets"
    />

    <VersionDrawer
      :visible="drawerVisible"
      :target-id="drawerTargetId"
      @update:visible="(v: boolean) => (drawerVisible = v)"
      @updated="loadTargets"
    />

    <ElDialog
      :model-value="probeDialogVisible"
      :title="`测试连接 — ${probeTarget?.display_name ?? ''}`"
      width="min(520px, 92vw)"
      @update:model-value="closeProbeDialog"
    >
      <div v-if="probeResult" class="probe-body">
        <template v-if="probeResult.ok">
          <div class="probe-ok">
            <span class="probe-status ok">连接成功</span>
            <span class="probe-latency">{{ probeResult.latency_ms ?? '-' }} ms</span>
          </div>
          <p class="muted">
            端点返回了符合 Invoke 契约的响应，评测链路可用。
          </p>
        </template>
        <template v-else>
          <div class="probe-ok">
            <span class="probe-status fail">连接失败</span>
            <ElTag size="small" type="danger">{{ probeResult.error_code }}</ElTag>
          </div>
          <p class="probe-message">{{ probeResult.message }}</p>
          <p class="muted">
            错误信息已脱敏；请检查端点、认证配置与网络连通性。
          </p>
        </template>
      </div>
      <div v-else class="probe-body">
        <p class="muted">正在探测最新版本端点…</p>
      </div>
      <template #footer>
        <ElButton
          v-if="probeTarget"
          :disabled="probingId !== null"
          @click="runProbe(probeTarget)"
        >
          重新测试
        </ElButton>
        <ElButton type="primary" @click="closeProbeDialog">关闭</ElButton>
      </template>
    </ElDialog>
  </PageContainer>
</template>

<style scoped lang="scss">
.stats-container {
  display: flex;
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-lg);
  flex-wrap: wrap;
}

.stat-card {
  flex: 1;
  min-width: 110px;
  padding: var(--spacing-lg);
  background-color: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-card);
  text-align: center;

  .stat-value {
    font-size: 28px;
    font-weight: var(--font-weight-bold);
    color: var(--text-primary);
    line-height: 1.2;
  }

  .stat-label {
    font-size: var(--font-size-small);
    color: var(--text-secondary);
    margin-top: var(--spacing-xs);
  }
}

.action-bar {
  display: flex;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
  align-items: center;

  .filters {
    margin-left: auto;
    display: flex;
    gap: var(--spacing-sm);

    .search-input {
      width: 240px;
    }

    .type-select {
      width: 120px;
    }
  }
}

.target-table {
  border-radius: var(--radius-card);
  overflow: hidden;

  .name-cell {
    display: flex;
    flex-direction: column;
    gap: 2px;

    .target-name {
      font-weight: var(--font-weight-medium);
      color: var(--text-primary);
    }

    .target-id {
      font-size: var(--font-size-small);
      color: var(--text-secondary);
    }
  }

  .endpoint {
    font-size: var(--font-size-small);
  }
}

.mono {
  font-family: var(--font-family-mono, monospace);
}

.muted {
  color: var(--text-secondary);
  font-size: var(--font-size-small);
}

.probe-body {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);

  .probe-ok {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);

    .probe-status {
      font-size: 16px;
      font-weight: var(--font-weight-medium);

      &.ok {
        color: var(--color-success);
      }

      &.fail {
        color: var(--color-danger);
      }
    }

    .probe-latency {
      color: var(--text-secondary);
      font-size: var(--font-size-small);
    }
  }

  .probe-message {
    font-family: var(--font-family-mono, monospace);
    font-size: var(--font-size-small);
    word-break: break-all;
    background: var(--bg-card, #f5f7fa);
    border-radius: var(--radius-card, 8px);
    padding: var(--spacing-sm);
    margin: 0;
  }
}
</style>
