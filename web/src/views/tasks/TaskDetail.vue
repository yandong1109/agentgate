<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElTag,
  ElDescriptions,
  ElDescriptionsItem,
} from 'element-plus'
import { tasksApi } from '@/api/tasks'
import type { Task, TaskRun } from '@/api/tasks'
import PageContainer from '@/components/PageContainer.vue'

const router = useRouter()
const route = useRoute()

const taskId = route.params.taskId as string
const task = ref<Task | null>(null)
const runs = ref<TaskRun[]>([])
const loading = ref(false)

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

function formatDate(dateStr: string | undefined | null) {
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

function goBack() {
  router.back()
}

function viewRunDetail(run: any) {
  router.push(`/tasks/${taskId}/runs/${run.id}`)
}

async function loadData() {
  loading.value = true
  try {
    const [taskDetail, runsList] = await Promise.all([
      tasksApi.detail(taskId),
      tasksApi.runs(taskId),
    ])
    task.value = taskDetail
    runs.value = runsList
  } catch (error) {
    console.error('加载任务详情失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <PageContainer title="任务详情" description="">
    <div class="back-btn">
      <ElButton @click="goBack">返回</ElButton>
    </div>

    <div v-if="task" class="task-detail">
      <!-- 任务基本信息 -->
      <ElDescriptions title="任务信息" :column="2" border>
        <ElDescriptionsItem label="任务名称">{{ task.task_name }}</ElDescriptionsItem>
        <ElDescriptionsItem label="状态">
          <ElTag :type="getStatusInfo(task.status).type as any">
            {{ getStatusInfo(task.status).label }}
          </ElTag>
        </ElDescriptionsItem>
        <ElDescriptionsItem label="评测对象快照">{{ task.target_name || task.target_id }}</ElDescriptionsItem>
        <ElDescriptionsItem label="评测集快照">{{ task.dataset_name || task.dataset_id }}</ElDescriptionsItem>
        <ElDescriptionsItem label="评估器快照">{{ task.evaluator_name || task.evaluator_id }}</ElDescriptionsItem>
        <ElDescriptionsItem label="创建时间">{{ formatDate(task.created_at) }}</ElDescriptionsItem>
      </ElDescriptions>

      <!-- 执行记录列表 -->
      <div class="runs-section">
        <h3>执行记录</h3>
        <ElTable :data="runs" stripe v-loading="loading">
          <ElTableColumn prop="run_no" label="执行次数" width="100" align="center">
            <template #default="{ row }">
              第{{ row.run_no }}次
            </template>
          </ElTableColumn>
          <ElTableColumn prop="status" label="状态" width="100" align="center">
            <template #default="{ row }">
              <ElTag :type="getStatusInfo(row.status).type as any">
                {{ getStatusInfo(row.status).label }}
              </ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="total_cases" label="总用例数" width="100" align="center" />
          <ElTableColumn prop="completed_cases" label="完成数" width="100" align="center" />
          <ElTableColumn prop="passed_cases" label="通过数" width="100" align="center" />
          <ElTableColumn prop="pass_rate" label="通过率" width="100" align="center">
            <template #default="{ row }">
              {{ row.pass_rate }}%
            </template>
          </ElTableColumn>
          <ElTableColumn prop="avg_score" label="平均分" width="100" align="center">
            <template #default="{ row }">
              {{ row.avg_score?.toFixed(1) || '-' }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="started_at" label="开始时间" width="160">
            <template #default="{ row }">
              {{ formatDate(row.started_at) }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="completed_at" label="完成时间" width="160">
            <template #default="{ row }">
              {{ formatDate(row.completed_at) }}
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <ElButton type="primary" size="small" @click="viewRunDetail(row)">
                明细
              </ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
      </div>
    </div>
  </PageContainer>
</template>

<style scoped lang="scss">
.back-btn {
  margin-bottom: var(--spacing-lg);
}

.task-detail {
  .runs-section {
    margin-top: var(--spacing-xl);

    h3 {
      margin-bottom: var(--spacing-md);
      font-size: var(--font-size-medium);
      color: var(--text-primary);
    }
  }
}
</style>
