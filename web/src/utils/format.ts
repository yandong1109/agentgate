// 格式化工具（从 App.vue L55-L58 / L160-L164 抽出）
import type { Outcome, ComparisonStatus } from '@/types/result'
import type { RunTarget } from '@/types/target'

/** Agent 显示标签："name · version" */
export function agentLabel(target: RunTarget): string {
  const name = target.display_name || target.ref.external_target_id
  return `${name} · ${target.ref.external_version_id}`
}

/** 分数转百分比，null → "N/A" */
export function asPercent(score: number | null): string {
  return score === null ? 'N/A' : `${Math.round(score * 100)}%`
}

export const outcomeText: Record<string, string> = {
  pass: '通过',
  fail: '失败',
  review: '待复核',
  not_applicable: '不适用',
  error: '评估错误',
}

export function outcomeType(
  outcome: string,
): 'success' | 'info' | 'warning' | 'danger' {
  if (outcome === 'pass') return 'success'
  if (outcome === 'not_applicable') return 'info'
  if (outcome === 'review') return 'warning'
  return 'danger'
}

export const comparisonText: Record<string, string> = {
  improved: '改善',
  regressed: '退化',
  mixed: '有改善也有退化',
  unchanged: '无变化',
  incomparable: '不可比较',
}

export function comparisonType(
  status: string,
): 'success' | 'info' | 'warning' | 'danger' {
  if (status === 'improved') return 'success'
  if (status === 'regressed' || status === 'mixed') return 'danger'
  if (status === 'unchanged') return 'info'
  return 'warning'
}

export type { Outcome, ComparisonStatus }
