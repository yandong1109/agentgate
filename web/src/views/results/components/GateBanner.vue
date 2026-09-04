<script setup lang="ts">
// Gate 决策横幅：醒目大色块显示发布门槛通过/未通过 + 关键数字
import { computed } from 'vue'
import { Check, Close } from '@element-plus/icons-vue'
import type { Gate } from '@/types/result'
import { asPercent } from '@/utils/format'

const props = defineProps<{ gate: Gate }>()

const passed = computed(() => props.gate.outcome === 'pass')
const totalCases = computed(() => props.gate.passed + props.gate.failed + props.gate.not_applicable + props.gate.reviewed + props.gate.errors)
const passRate = computed(() => (totalCases.value > 0 ? props.gate.passed / totalCases.value : 0))
</script>

<template>
  <div class="gate-banner" :class="passed ? 'is-pass' : 'is-fail'">
    <div class="gate-icon">
      <component :is="passed ? Check : Close" />
    </div>
    <div class="gate-text">
      <b class="gate-title">{{ passed ? '发布门槛通过' : '发布门槛未通过' }}</b>
      <small class="gate-reason">{{ gate.reason }}</small>
    </div>
    <div class="gate-stats">
      <div class="gate-stat">
        <b>{{ asPercent(passRate) }}</b>
        <small>通过率</small>
      </div>
      <div class="gate-stat">
        <b>{{ gate.passed }}</b>
        <small>通过</small>
      </div>
      <div class="gate-stat gate-stat-fail">
        <b>{{ gate.failed }}</b>
        <small>失败</small>
      </div>
      <div class="gate-stat">
        <b>{{ Math.round(gate.threshold * 100) }}%</b>
        <small>门槛</small>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.gate-banner {
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
  padding: var(--spacing-lg) var(--spacing-xl);
  border-radius: var(--radius-card);
  border-left: 4px solid var(--border-color);

  &.is-pass {
    background-color: var(--color-primary-lighter);
    border-left-color: var(--color-primary);

    .gate-icon {
      background-color: var(--color-primary);
    }

    .gate-title {
      color: var(--color-primary-active);
    }
  }

  &.is-fail {
    background-color: var(--color-danger-lighter, #fef2f2);
    border-left-color: var(--color-danger);

    .gate-icon {
      background-color: var(--color-danger);
    }

    .gate-title {
      color: var(--color-danger);
    }
  }
}

.gate-icon {
  flex: 0 0 auto;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 700;
}

.gate-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.gate-title {
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-bold);
}

.gate-reason {
  font-size: var(--font-size-small);
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}

.gate-stats {
  display: flex;
  gap: var(--spacing-xl);
  flex: 0 0 auto;
  flex-wrap: wrap;
}

.gate-stat {
  text-align: right;

  b {
    display: block;
    font-size: var(--font-size-h4);
    font-weight: var(--font-weight-bold);
    color: var(--text-primary);
    font-family: var(--font-family-mono);
    line-height: 1.2;
  }

  small {
    font-size: var(--font-size-small);
    color: var(--text-secondary);
  }

  &.gate-stat-fail b {
    color: var(--color-danger);
  }
}

@media (max-width: 768px) {
  .gate-banner {
    flex-wrap: wrap;
  }

  .gate-stats {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
