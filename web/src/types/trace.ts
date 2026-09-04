// Trace 域类型
import type { JsonObject } from './dataset'

export interface TraceTurn {
  turn_id: string
  input: JsonObject
  output: JsonObject
  state: JsonObject
}

export interface TraceSpan {
  id: string
  name: string
  kind: string
  sequence: number
  attributes: Record<string, unknown>
}

export interface Trace {
  case_id: string
  spans: TraceSpan[]
  turns: TraceTurn[]
  final_state: Record<string, unknown>
  final_output: Record<string, unknown>
}
