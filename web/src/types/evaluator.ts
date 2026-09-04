// Evaluator 域类型
export interface EvaluatorOption {
  id: string
  name: string
  kind: 'rule' | 'llm_judge' | 'hybrid'
  version: string
  dimension: string
  metric: string
  severity: 'standard' | 'blocking'
  evaluator_type: string
  operator: string | null
  /** 来源：内置（只读）/ 自定义（可读写）。后端未补字段时默认 builtin */
  source?: 'builtin' | 'user'
}
