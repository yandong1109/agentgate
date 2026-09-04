<script setup lang="ts">
// 404 页面
import { ElButton } from 'element-plus'
import { useRouter } from 'vue-router'

const router = useRouter()
function goHome() {
  router.push('/runs')
}
</script>

<template>
  <section class="not-found">
    <div class="not-found-card">
      <div class="not-found-code">404</div>
      <h1 class="not-found-title">页面不存在</h1>
      <p class="not-found-desc">你访问的页面已被移动、删除或从未存在。</p>
      <ElButton type="primary" @click="goHome">返回首页</ElButton>
    </div>
  </section>
</template>

<style scoped lang="scss">
.not-found {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 70vh;
  padding: var(--spacing-3xl);
}

.not-found-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: var(--spacing-md);
  padding: var(--spacing-4xl);
  background-color: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-card);
  max-width: 480px;
  width: 100%;
}

.not-found-code {
  font-family: var(--font-family-mono);
  font-size: 96px;
  font-weight: var(--font-weight-bold);
  line-height: 1;
  color: var(--color-primary);
}

.not-found-title {
  font-size: var(--font-size-h3);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
}

.not-found-desc {
  font-size: var(--font-size-body);
  color: var(--text-secondary);
  margin: 0;
}
</style>
