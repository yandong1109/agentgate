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
  ElDialog,
} from 'element-plus'
import { tasksApi } from '@/api/tasks'
import type { TaskRun, CaseExecution } from '@/api/tasks'
import { http } from '@/utils/request'
import PageContainer from '@/components/PageContainer.vue'

const router = useRouter()
const route = useRoute()

const taskId = route.params.taskId as string
const runId = route.params.runId as string

const run = ref<TaskRun | null>(null)
const caseExecutions = ref<CaseExecution[]>([])
const targetSnapshot = ref<any>(null)
const datasetSnapshot = ref<any>(null)
const evaluatorSnapshot = ref<any>(null)
const loading = ref(false)

// 用例详情弹窗
const caseDialogVisible = ref(false)
const selectedCase = ref<CaseExecution | null>(null)
const caseDetail = ref<any>(null)

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

function viewCaseDetail(caseExec: any) {
  selectedCase.value = caseExec
  // 获取用例详情
  caseDetail.value = null
  http.get<{ data: any }>(`/api/tasks/cases/${caseExec.case_id}`)
    .then(resp => {
      caseDetail.value = resp.data
    })
    .catch(e => {
      console.error('获取用例详情失败:', e)
      caseDetail.value = { case_data: {} }
    })
  caseDialogVisible.value = true
}

async function loadData() {
  loading.value = true
  try {
    // 获取执行记录列表
    const runsList = await tasksApi.runs(taskId)
    run.value = runsList.find(r => r.id === runId) || null

    if (!run.value) {
      console.error('执行记录不存在')
      return
    }

    // 获取用例执行列表（通过API）
    try {
      const response = await http.get<{ content: CaseExecution[] }>(`/api/runs/${runId}/cases`)
      caseExecutions.value = response.content || []
    } catch (e) {
      // 如果API不存在，使用空数组
      caseExecutions.value = []
    }

    // 快照信息
    if (run.value.target_snapshot_id) {
      try {
        const resp = await http.get<{ data: any }>(`/api/tasks/snapshots/target/${run.value.target_snapshot_id}`)
        targetSnapshot.value = resp.data
      } catch (e) {
        targetSnapshot.value = {
          id: run.value.target_snapshot_id,
          agent_type: '-',
          snapshot_data: { message: '加载失败' }
        }
      }
    } else {
      targetSnapshot.value = null
    }

    if (run.value.dataset_snapshot_id) {
      try {
        const resp = await http.get<{ data: any }>(`/api/tasks/snapshots/dataset/${run.value.dataset_snapshot_id}`)
        datasetSnapshot.value = resp.data
      } catch (e) {
        datasetSnapshot.value = {
          id: run.value.dataset_snapshot_id,
          case_count: 0,
          snapshot_data: { message: '加载失败' }
        }
      }
    } else {
      datasetSnapshot.value = null
    }

    if (run.value.evaluator_snapshot_id) {
      try {
        const resp = await http.get<{ data: any }>(`/api/tasks/snapshots/evaluator/${run.value.evaluator_snapshot_id}`)
        evaluatorSnapshot.value = resp.data
      } catch (e) {
        evaluatorSnapshot.value = {
          id: run.value.evaluator_snapshot_id,
          evaluator_type: '-',
          snapshot_data: { message: '加载失败' }
        }
      }
    } else {
      evaluatorSnapshot.value = null
    }

  } catch (error) {
    console.error('加载执行详情失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <PageContainer title="执行详情" description="">
    <div class="back-btn">
      <ElButton @click="goBack">返回</ElButton>
    </div>

    <div v-if="run" class="run-detail" v-loading="loading">
      <!-- 执行记录信息 -->
      <ElDescriptions title="执行记录" :column="2" border style="margin-bottom: var(--spacing-lg)">
        <ElDescriptionsItem label="执行次数">第{{ run.run_no }}次</ElDescriptionsItem>
        <ElDescriptionsItem label="状态">
          <ElTag :type="getStatusInfo(run.status).type as any">
            {{ getStatusInfo(run.status).label }}
          </ElTag>
        </ElDescriptionsItem>
        <ElDescriptionsItem label="总用例数">{{ run.total_cases }}</ElDescriptionsItem>
        <ElDescriptionsItem label="完成数">{{ run.completed_cases }}</ElDescriptionsItem>
        <ElDescriptionsItem label="通过数">{{ run.passed_cases }}</ElDescriptionsItem>
        <ElDescriptionsItem label="通过率">{{ run.pass_rate }}%</ElDescriptionsItem>
        <ElDescriptionsItem label="平均分">{{ run.avg_score?.toFixed(1) || '-' }}</ElDescriptionsItem>
        <ElDescriptionsItem label="开始时间">{{ formatDate(run.started_at) }}</ElDescriptionsItem>
      </ElDescriptions>

      <!-- 评测对象快照信息 -->
      <ElDescriptions v-if="targetSnapshot" title="评测对象快照" :column="2" border style="margin-bottom: var(--spacing-lg)">
        <ElDescriptionsItem label="快照ID">{{ targetSnapshot.id }}</ElDescriptionsItem>
        <ElDescriptionsItem label="类型">{{ targetSnapshot.agent_type || '-' }}</ElDescriptionsItem>
        <ElDescriptionsItem label="配置信息" :span="2">
          <pre style="margin: 0; white-space: pre-wrap;">{{ JSON.stringify(targetSnapshot.snapshot_data, null, 2) }}</pre>
        </ElDescriptionsItem>
      </ElDescriptions>

      <!-- 测评集快照信息 -->
      <ElDescriptions v-if="datasetSnapshot" title="测评集快照" :column="2" border style="margin-bottom: var(--spacing-lg)">
        <ElDescriptionsItem label="快照ID">{{ datasetSnapshot.id }}</ElDescriptionsItem>
        <ElDescriptionsItem label="用例数量">{{ datasetSnapshot.case_count || '-' }}</ElDescriptionsItem>
        <ElDescriptionsItem label="快照数据" :span="2">
          <pre style="margin: 0; white-space: pre-wrap;">{{ JSON.stringify(datasetSnapshot.snapshot_data, null, 2) }}</pre>
        </ElDescriptionsItem>
      </ElDescriptions>

      <!-- 评估器快照信息 -->
      <ElDescriptions v-if="evaluatorSnapshot" title="评估器快照" :column="2" border style="margin-bottom: var(--spacing-lg)">
        <ElDescriptionsItem label="快照ID">{{ evaluatorSnapshot.id }}</ElDescriptionsItem>
        <ElDescriptionsItem label="类型">{{ evaluatorSnapshot.evaluator_type || '-' }}</ElDescriptionsItem>
        <ElDescriptionsItem label="配置信息" :span="2">
          <pre style="margin: 0; white-space: pre-wrap;">{{ JSON.stringify(evaluatorSnapshot.snapshot_data, null, 2) }}</pre>
        </ElDescriptionsItem>
      </ElDescriptions>

      <!-- 用例执行列表 -->
      <div class="cases-section">
        <h3>用例执行明细</h3>
        <ElTable :data="caseExecutions" stripe>
          <ElTableColumn prop="case_id" label="用例ID" min-width="150" />
          <ElTableColumn prop="status" label="状态" width="100" align="center">
            <template #default="{ row }">
              <ElTag :type="getStatusInfo(row.status).type as any">
                {{ getStatusInfo(row.status).label }}
              </ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="score" label="得分" width="80" align="center">
            <template #default="{ row }">
              {{ row.score?.toFixed(1) || '-' }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="passed" label="是否通过" width="100" align="center">
            <template #default="{ row }">
              <ElTag :type="row.passed ? 'success' : 'danger'">
                {{ row.passed ? '通过' : '失败' }}
              </ElTag>
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
              <ElButton type="primary" size="small" @click="viewCaseDetail(row)">
                明细
              </ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
      </div>
    </div>

    <!-- 用例详情弹窗 -->
    <ElDialog v-model="caseDialogVisible" title="用例详情" width="min(900px, 95vw)">
      <div v-if="selectedCase">
        <ElDescriptions :column="2" border style="margin-bottom: var(--spacing-lg)">
          <ElDescriptionsItem label="用例ID">{{ selectedCase.case_id }}</ElDescriptionsItem>
          <ElDescriptionsItem label="用例名称">{{ caseDetail?.name || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="状态">
            <ElTag :type="getStatusInfo(selectedCase.status).type as any">
              {{ getStatusInfo(selectedCase.status).label }}
            </ElTag>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="是否通过">
            <ElTag :type="selectedCase.passed ? 'success' : 'danger'">
              {{ selectedCase.passed ? '通过' : '失败' }}
            </ElTag>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="得分">{{ selectedCase.score?.toFixed(1) || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="标签">{{ caseDetail?.tags || '-' }}</ElDescriptionsItem>
        </ElDescriptions>

        <!-- 用例配置信息 -->
        <div class="response-section" v-if="caseDetail?.case_data">
          <h4>用例配置信息</h4>
          <div class="response-content">
            <pre>{{ JSON.stringify(caseDetail.case_data, null, 2) }}</pre>
          </div>
        </div>

        <!-- Agent执行轨迹 -->
        <div class="response-section" v-if="selectedCase.trace_data">
          <h4>Agent执行轨迹</h4>
          <div class="trace-content">
            <div v-if="selectedCase.trace_data.session_id" class="trace-item">
              <span class="trace-label">Session ID:</span>
              <span class="trace-value">{{ selectedCase.trace_data.session_id }}</span>
            </div>
            <div v-if="selectedCase.trace_data.rounds" class="rounds-section">
              <div v-for="(round, idx) in selectedCase.trace_data.rounds" :key="idx" class="round-item">
                <div class="round-header">第 {{ round.round || (idx + 1) }} 轮</div>
                <div class="round-content">
                  <div class="message user-message">
                    <span class="message-label">用户输入:</span>
                    <span class="message-text">{{ round.user_input || round.user || '-' }}</span>
                  </div>
                  <div class="message agent-message">
                    <span class="message-label">Agent回复:</span>
                    <span class="message-text">{{ round.agent_response || round.response || '-' }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Agent返回信息 -->
        <div class="response-section">
          <h4>Agent返回信息（汇总）</h4>
          <div class="response-content">
            {{ selectedCase.agent_response || '无' }}
          </div>
        </div>
      </div>
      <template #footer>
        <ElButton @click="caseDialogVisible = false">关闭</ElButton>
      </template>
    </ElDialog>
  </PageContainer>
</template>

<style scoped lang="scss">
.back-btn {
  margin-bottom: var(--spacing-lg);
}

.cases-section {
  margin-top: var(--spacing-xl);

  h3 {
    margin-bottom: var(--spacing-md);
    font-size: var(--font-size-medium);
    color: var(--text-primary);
  }
}

.response-section {
  margin-top: var(--spacing-lg);

  h4 {
    margin-bottom: var(--spacing-sm);
    font-size: var(--font-size-small);
    color: var(--text-secondary);
  }

  .response-content {
    padding: var(--spacing-md);
    background-color: var(--bg-page);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-small);
    white-space: pre-wrap;
    max-height: 300px;
    overflow-y: auto;
    font-family: monospace;
    font-size: var(--font-size-small);
  }

  .trace-content {
    padding: var(--spacing-md);
    background-color: var(--bg-page);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-small);
    max-height: 400px;
    overflow-y: auto;

    .trace-item {
      margin-bottom: var(--spacing-sm);
      font-family: monospace;
      font-size: var(--font-size-small);

      .trace-label {
        color: var(--text-secondary);
        margin-right: var(--spacing-xs);
      }
      .trace-value {
        color: var(--text-primary);
      }
    }

    .rounds-section {
      margin-top: var(--spacing-md);

      .round-item {
        margin-bottom: var(--spacing-lg);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-small);
        overflow: hidden;

        .round-header {
          padding: var(--spacing-sm) var(--spacing-md);
          background-color: var(--bg-card);
          font-weight: var(--font-weight-medium);
          font-size: var(--font-size-small);
          color: var(--text-primary);
        }

        .round-content {
          padding: var(--spacing-md);

          .message {
            margin-bottom: var(--spacing-md);
            &:last-child {
              margin-bottom: 0;
            }

            .message-label {
              display: block;
              font-size: var(--font-size-small);
              color: var(--text-secondary);
              margin-bottom: var(--spacing-xs);
            }

            .message-text {
              display: block;
              padding: var(--spacing-sm);
              background-color: var(--bg-page);
              border-radius: var(--radius-small);
              font-family: monospace;
              font-size: var(--font-size-small);
              white-space: pre-wrap;
            }
          }

          .user-message .message-label {
            color: var(--color-primary);
          }

          .agent-message .message-label {
            color: var(--color-success);
          }
        }
      }
    }
  }
}
</style>
