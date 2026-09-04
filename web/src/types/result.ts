// Result 域类型
import type { Run } from './target'

export interface Evidence {
  trace_id: string
  span_ids: string[]
  description: string
}

export type Outcome = 'pass' | 'fail' | 'review' | 'not_applicable' | 'error'

/** 评估方法引用：对比算子（equals/contains_all/...），来自后端 CheckResult.methods */
export interface MethodRef {
  operator: string
  operator_version: string
  condition_kind?: string | null
}

export interface CheckResult {
  id: string
  name: string
  turn_id: string | null
  expectation_id: string | null
  outcome: Outcome
  score: number | null
  reason: string
  expected: unknown
  actual: unknown
  actual_missing: boolean
  methods?: MethodRef[]
  evidence: Evidence[]
}

export interface Result {
  case_id: string
  evaluator_id: string
  evaluator_name: string
  evaluator_kind: string
  dimension: string
  metric: string
  severity: 'standard' | 'blocking'
  outcome: Outcome
  score: number | null
  reason: string
  primary_failure_step?: string
  evidence: Evidence[]
  checks: CheckResult[]
}

export interface Gate {
  outcome: 'pass' | 'fail'
  passed: number
  failed: number
  reviewed: number
  not_applicable: number
  errors: number
  score: number | null
  threshold: number
  reason: string
}

export interface Metric {
  key: string
  label: string
  level: 'overall' | 'kind' | 'dimension' | 'metric'
  score: number | null
  passed: number
  failed: number
  reviewed: number
  not_applicable: number
  errors: number
  applicable: number
  total: number
  incomplete: boolean
}

export interface Report {
  run: Run
  results: Result[]
  gate: Gate
  metrics: Metric[]
}

export type ComparisonStatus = 'improved' | 'regressed' | 'unchanged' | 'incomparable'

export interface RerunComparison {
  root_run_id: string
  parent_run_id: string
  rerun_run_id: string
  case_id: string
  case_name: string
  before_target_version: string
  after_target_version: string
  overall: ComparisonStatus | 'mixed'
  counts: Record<ComparisonStatus, number>
  evaluators: {
    evaluator_id: string
    evaluator_name: string
    status: ComparisonStatus
    before: { outcome: Outcome; score: number | null; reason: string } | null
    after: { outcome: Outcome; score: number | null; reason: string } | null
  }[]
}
