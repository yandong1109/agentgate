<script setup lang="ts">
// 调优中心页（占位，P2 阶段实现）
import PageContainer from '@/components/PageContainer.vue'
import ComingSoon from '@/components/ComingSoon.vue'
</script>

<template>
  <PageContainer title="调优中心" description="基于评测结果驱动的优化器与建议。">
    <ComingSoon
      title="调优中心"
      description="结合评测结果与调用链血缘，提供优化器建议、Prompt 迭代与回归追踪，将在 P2 阶段交付。"
      phase="P2"
    />
  </PageContainer>
</template>
