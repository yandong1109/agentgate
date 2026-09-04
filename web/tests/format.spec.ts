import { describe, it, expect } from 'vitest'
import {
  agentLabel,
  asPercent,
  outcomeType,
  comparisonType,
  outcomeText,
  comparisonText,
} from '@/utils/format'
import type { RunTarget } from '@/types/target'

// format.ts 是从旧 App.vue 抽出的共享纯逻辑（多 view 复用），
// 一人改坏会全局波及，作为 Vitest 快速层起步集优先覆盖。

const baseTarget: RunTarget = {
  ref: { external_target_id: 'loan-agent', external_version_id: 'v1' },
  display_name: '风险版本',
  adapter_type: 'python_fn',
}

describe('agentLabel', () => {
  it('renders display_name · version when display_name present', () => {
    expect(agentLabel(baseTarget)).toBe('风险版本 · v1')
  })

  it('falls back to external_target_id when display_name is empty', () => {
    expect(agentLabel({ ...baseTarget, display_name: '' })).toBe('loan-agent · v1')
  })
})

describe('asPercent', () => {
  it('converts score to rounded percent', () => {
    expect(asPercent(0.25)).toBe('25%')
    expect(asPercent(0.256)).toBe('26%')
    expect(asPercent(1)).toBe('100%')
    expect(asPercent(0)).toBe('0%')
  })

  it('renders N/A for null score', () => {
    expect(asPercent(null)).toBe('N/A')
  })
})

describe('outcomeType', () => {
  it.each([
    ['pass', 'success'],
    ['not_applicable', 'info'],
    ['review', 'warning'],
  ] as const)('maps %s to %s', (outcome, expected) => {
    expect(outcomeType(outcome)).toBe(expected)
  })

  it('defaults fail/unknown to danger', () => {
    expect(outcomeType('fail')).toBe('danger')
    expect(outcomeType('error')).toBe('danger')
    expect(outcomeType('whatever')).toBe('danger')
  })
})

describe('comparisonType', () => {
  it.each([
    ['improved', 'success'],
    ['unchanged', 'info'],
    ['incomparable', 'warning'],
  ] as const)('maps %s to %s', (status, expected) => {
    expect(comparisonType(status)).toBe(expected)
  })

  it('maps regressed and mixed to danger', () => {
    expect(comparisonType('regressed')).toBe('danger')
    expect(comparisonType('mixed')).toBe('danger')
  })
})

describe('text maps', () => {
  it('exposes stable chinese labels for outcomes', () => {
    expect(outcomeText.pass).toBe('通过')
    expect(outcomeText.fail).toBe('失败')
    expect(outcomeText.not_applicable).toBe('不适用')
  })

  it('exposes stable chinese labels for comparison status', () => {
    expect(comparisonText.improved).toBe('改善')
    expect(comparisonText.regressed).toBe('退化')
  })
})
