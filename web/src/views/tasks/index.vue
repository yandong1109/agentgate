<script setup lang="ts">
// 任务管理页面
import { computed, onMounted, ref, shallowRef } from 'vue'
import { useRouter } from 'vue-router'
import {
  ElMessage,
  ElMessageBox,
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElSelect,
  ElOption,
  ElTag,
  ElTable,
  ElTableColumn,
  ElPagination,
} from 'element-plus'
import { tasksApi } from '@/api/tasks'
import type { Task, TaskRun } from '@/api/tasks'
import { targetsApi } from '@/api/targets'
import { datasetsApi } from '@/api/datasets'
import { evaluatorsApi } from '@/api/evaluators'
import PageContainer from '@/components/PageContainer.vue'
import type { TargetOption, DatasetOption, EvaluatorOption } from '@/types/task'

const router = useRouter()

const tasks = shallowRef<Task[]>([])
const loading = ref(false)
const busy = ref(false)
const totalElements = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)

// 统计数据
const stats = computed(() => {
  const all = tasks.value
  return {
    total: all.length,
    running: all.filter((t) => t.status === 'RUNNING').length,
    pending: all.filter((t) => t.status === 'PENDING').length,
    success: all.filter((t) => t.status === 'SUCCESS').length,
    fail: all.filter((t) => t.status === 'FAIL').length,
  }
})

// 创建任务弹窗
const createDialogVisible = ref(false)
const createForm = ref({
  task_name: '',
  target_id: '',
  dataset_id: '',
  evaluator_id: '',
})

// 下拉选项数据
const targetOptions = ref<TargetOption[]>([])
const datasetOptions = ref<DatasetOption[]>([])
const evaluatorOptions = ref<EvaluatorOption[]>([])

// 状态映射
const statusMap: Record<string, { label: string; type: string }> = {
  NEW: { label: '新建', type: 'info' },
  PENDING: { label: '待执行', type: 'warning' },
  RUNNING: { label: '执行中', type: 'primary' },
  SUCCESS: { label: '成功', type: 'success' },
  FAIL: { label: '失败', type: 'danger' },
  TERMINATED: { label: '已终止', type: 'info' },
}

function getStatusInfo(status: string) {
  return statusMap[status] || { label: status, type: 'info' }
}

function formatDate(dateStr: string | undefined) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

async function loadTasks() {
  loading.value = true
  try {
    const response = await tasksApi.list({
      page: currentPage.value - 1,
      size: pageSize.value,
    })
    tasks.value = response.content
    totalElements.value = response.total_elements
  } catch (error) {
    ElMessage.error('加载任务列表失败')
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  try {
    const [targets, datasets, evaluators] = await Promise.all([
      targetsApi.versions ? targetsApi.versions() : Promise.resolve([]),
      datasetsApi.list(),
      evaluatorsApi.evaluators(),
    ])
    // 根据实际情况调整数据格式
    targetOptions.value = Array.isArray(targets) ? targets.map((t: any) => ({
      id: t.id,
      agent_name: t.agent_name || t.label || t.id,
      agent_type: t.agent_type || t.adapter_type || 'REMOTE_AGENT',
      status: 'ACTIVE',
    })) : []
    datasetOptions.value = Array.isArray(datasets) ? datasets.map((d: any) => ({
      id: d.id,
      name: d.name,
      description: d.description || '',
    })) : []
    evaluatorOptions.value = Array.isArray(evaluators) ? evaluators.map((e: any) => ({
      id: e.id,
      name: e.name,
      evaluator_type: e.evaluator_type || 'RULE',
    })) : []
  } catch (error) {
    console.error('加载选项失败:', error)
  }
}

function openCreateDialog() {
  createForm.value = {
    task_name: '',
    target_id: '',
    dataset_id: '',
    evaluator_id: '',
  }
  createDialogVisible.value = true
}

async function submitCreateDialog() {
  if (!createForm.value.task_name.trim()) {
    return ElMessage.warning('请输入任务名称')
  }
  if (!createForm.value.target_id) {
    return ElMessage.warning('请选择评测对象')
  }
  if (!createForm.value.dataset_id) {
    return ElMessage.warning('请选择测评集')
  }
  if (!createForm.value.evaluator_id) {
    return ElMessage.warning('请选择评估器')
  }

  busy.value = true
  try {
    await tasksApi.create(createForm.value)
    ElMessage.success('任务创建成功')
    createDialogVisible.value = false
    await loadTasks()
  } catch (error) {
    ElMessage.error('创建任务失败')
  } finally {
    busy.value = false
  }
}

async function handleStartTask(task: any) {
  try {
    await ElMessageBox.confirm(`确定启动任务"${task.task_name}"吗？`, '启动任务', {
      type: 'info',
    })
    await tasksApi.start(task.id)
    ElMessage.success('任务已启动')
    await loadTasks()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '启动任务失败')
    }
  }
}

async function handleStopTask(task: any) {
  try {
    await ElMessageBox.confirm(`确定停止任务"${task.task_name}"吗？`, '停止任务', {
      type: 'warning',
    })
    await tasksApi.stop(task.id, '用户手动停止')
    ElMessage.success('任务已停止')
    await loadTasks()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '停止任务失败')
    }
  }
}

async function handleDeleteTask(task: any) {
  try {
    await ElMessageBox.confirm(`确定删除任务"${task.task_name}"吗？此操作不可恢复。`, '删除任务', {
      type: 'warning',
    })
    await tasksApi.delete(task.id)
    ElMessage.success('任务已删除')
    await loadTasks()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除任务失败')
    }
  }
}

function handlePageChange(page: number) {
  currentPage.value = page
  loadTasks()
}

function handleSizeChange(size: number) {
  pageSize.value = size
  currentPage.value = 1
  loadTasks()
}

function viewTaskDetail(task: any) {
  router.push(`/tasks/${task.id}`)
}

onMounted(async () => {
  await Promise.all([loadTasks(), loadOptions()])
})
</script>

<template>
  <PageContainer title="任务管理" description="创建、启动、停止和管理评测任务。">
    <!-- 统计卡片 -->
    <div class="stats-container">
      <div class="stat-card">
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">全部任务</div>
      </div>
      <div class="stat-card running">
        <div class="stat-value">{{ stats.running }}</div>
        <div class="stat-label">执行中</div>
      </div>
      <div class="stat-card pending">
        <div class="stat-value">{{ stats.pending }}</div>
        <div class="stat-label">待执行</div>
      </div>
      <div class="stat-card success">
        <div class="stat-value">{{ stats.success }}</div>
        <div class="stat-label">成功</div>
      </div>
      <div class="stat-card fail">
        <div class="stat-value">{{ stats.fail }}</div>
        <div class="stat-label">失败</div>
      </div>
    </div>

    <!-- 操作栏 -->
    <div class="action-bar">
      <ElButton type="primary" @click="openCreateDialog">创建任务</ElButton>
      <ElButton @click="loadTasks">刷新</ElButton>
    </div>

    <!-- 任务列表 -->
    <ElTable
      v-loading="loading"
      :data="tasks"
      stripe
      class="task-table"
    >
      <ElTableColumn prop="task_name" label="任务名称" min-width="180">
        <template #default="{ row }">
          <span class="task-name">{{ row.task_name }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="target_name" label="评测对象" min-width="120">
        <template #default="{ row }">
          <span>{{ row.target_name || row.target_id }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="dataset_name" label="测评集" min-width="120">
        <template #default="{ row }">
          <span>{{ row.dataset_name || row.dataset_id }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="evaluator_name" label="评估器" min-width="120">
        <template #default="{ row }">
          <span>{{ row.evaluator_name || row.evaluator_id }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="status" label="状态" width="100" align="center">
        <template #default="{ row }">
          <ElTag :type="getStatusInfo(row.status).type as any">
            {{ getStatusInfo(row.status).label }}
          </ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="latest_run" label="最近执行" width="140">
        <template #default="{ row }">
          <div v-if="row.latest_run" class="run-info">
            <span>第{{ row.latest_run.run_no }}次</span>
            <span class="run-rate">{{ row.latest_run.pass_rate }}%</span>
          </div>
          <span v-else>-</span>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="created_at" label="创建时间" width="160">
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </ElTableColumn>
      <ElTableColumn label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <div class="action-buttons">
            <ElButton
              type="primary"
              size="small"
              @click="viewTaskDetail(row)"
            >
              明细
            </ElButton>
            <ElButton
              v-if="row.status === 'NEW'"
              type="primary"
              size="small"
              @click="handleStartTask(row)"
            >
              启动
            </ElButton>
            <ElButton
              v-if="row.status === 'PENDING' || row.status === 'RUNNING'"
              type="warning"
              size="small"
              @click="handleStopTask(row)"
            >
              停止
            </ElButton>
            <ElButton
              v-if="['NEW', 'SUCCESS', 'FAIL', 'TERMINATED'].includes(row.status)"
              type="danger"
              size="small"
              @click="handleDeleteTask(row)"
            >
              删除
            </ElButton>
          </div>
        </template>
      </ElTableColumn>
    </ElTable>

    <!-- 分页 -->
    <div class="pagination-container">
      <ElPagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="totalElements"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </div>

    <!-- 创建任务弹窗 -->
    <ElDialog
      v-model="createDialogVisible"
      title="创建任务"
      width="min(560px, 92vw)"
    >
      <ElForm label-position="top">
        <ElFormItem label="任务名称" required>
          <ElInput
            v-model="createForm.task_name"
            placeholder="请输入任务名称"
          />
        </ElFormItem>
        <ElFormItem label="评测对象" required>
          <ElSelect
            v-model="createForm.target_id"
            placeholder="请选择评测对象"
            style="width: 100%"
          >
            <ElOption
              v-for="item in targetOptions"
              :key="item.id"
              :label="item.agent_name"
              :value="item.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="测评集" required>
          <ElSelect
            v-model="createForm.dataset_id"
            placeholder="请选择测评集"
            style="width: 100%"
          >
            <ElOption
              v-for="item in datasetOptions"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="评估器" required>
          <ElSelect
            v-model="createForm.evaluator_id"
            placeholder="请选择评估器"
            style="width: 100%"
          >
            <ElOption
              v-for="item in evaluatorOptions"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </ElSelect>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="createDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="busy" @click="submitCreateDialog">确认创建</ElButton>
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
  min-width: 120px;
  padding: var(--spacing-lg);
  background-color: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-card);
  text-align: center;

  .stat-value {
    font-size: 32px;
    font-weight: var(--font-weight-bold);
    color: var(--text-primary);
    line-height: 1.2;
  }

  .stat-label {
    font-size: var(--font-size-small);
    color: var(--text-secondary);
    margin-top: var(--spacing-xs);
  }

  &.running {
    border-left: 3px solid var(--color-primary);
    .stat-value {
      color: var(--color-primary);
    }
  }

  &.pending {
    border-left: 3px solid var(--color-warning);
    .stat-value {
      color: var(--color-warning);
    }
  }

  &.success {
    border-left: 3px solid var(--color-success);
    .stat-value {
      color: var(--color-success);
    }
  }

  &.fail {
    border-left: 3px solid var(--color-danger);
    .stat-value {
      color: var(--color-danger);
    }
  }
}

.action-bar {
  display: flex;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

.task-table {
  border-radius: var(--radius-card);
  overflow: hidden;

  .task-name {
    font-weight: var(--font-weight-medium);
    color: var(--text-primary);
  }

  .run-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: var(--font-size-small);

    .run-rate {
      color: var(--color-success);
      font-weight: var(--font-weight-medium);
    }
  }

  .action-buttons {
    display: flex;
    gap: var(--spacing-xs);
    flex-wrap: wrap;
  }
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--spacing-lg);
}
</style>
