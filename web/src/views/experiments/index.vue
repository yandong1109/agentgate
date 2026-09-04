<script setup lang="ts">
// A/B 实验页（占位，P2 阶段实现）
import PageContainer from '@/components/PageContainer.vue'
import ComingSoon from '@/components/ComingSoon.vue'
</script>

<template>
  <PageContainer title="A/B 实验" description="对不同 Agent 版本进行对照实验。">
    <ComingSoon
      title="A/B 实验中心"
      description="设计并运行 Agent 版本之间的 A/B 对照实验，自动统计差异显著性，将在 P2 阶段交付。"
      phase="P2"
    />
  </PageContainer>
</template>
