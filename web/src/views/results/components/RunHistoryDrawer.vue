<script setup lang="ts">
// 运行记录抽屉：右侧抽屉选 Run，不离开结果页即可切换
// 复用 RecentRunsTable，点选后 emit open，抽屉保持打开可连续切
import { ElDrawer } from 'element-plus'
import type { Run } from '@/types/target'
import RecentRunsTable from './RecentRunsTable.vue'

const props = defineProps<{
  modelValue: boolean
  runs: Run[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  open: [id: string]
}>()

function onClose() {
  emit('update:modelValue', false)
}

function onOpen(id: string) {
  emit('open', id)
}
</script>

<template>
  <ElDrawer
    :model-value="modelValue"
    title="运行记录"
    direction="rtl"
    size="420px"
    @update:model-value="onClose"
  >
    <RecentRunsTable :runs="runs" @open="onOpen" />
  </ElDrawer>
</template>
