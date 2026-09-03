// Target/Integrations 域类型
import type { EvaluatorOption } from './evaluator'
import type { DatasetVersion } from './dataset'

export interface Version {
  id: string
  label: string
  is_latest: boolean
  adapter_type?: 'python_fn' | 'http'
  endpoint?: string
  credential_ref?: string | null
}

export interface Capability {
  name: string
  kind: string
  description: string
}

export interface TargetVersionInfo {
  id: string
  target_id: string
  version: number
  endpoint: string
  credential_ref: string | null
  invocation_config: { timeout_seconds?: number } & Record<string, unknown>
  capabilities: Capability[]
  content_sha256: string
  is_latest: boolean
  published_at: string
}

export interface TargetRecord {
  id: string
  display_name: string
  target_type: 'agent' | 'skill'
  adapter_type: string
  external_target_id: string
  platform_id: string
  description: string
  capabilities: Capability[]
  status: string
  created_at: string
  updated_at: string
}

export interface TargetListItem extends TargetRecord {
  version_count: number
  latest_version: TargetVersionInfo | null
}

export interface TargetDetail extends TargetRecord {
  versions: TargetVersionInfo[]
}

export interface ConnectionProbe {
  ok: boolean
  error_code?: string
  message?: string
  latency_ms?: number
  trace_id?: string | null
}

export interface RegisterTargetPayload {
  display_name: string
  endpoint: string
  target_type: 'agent' | 'skill'
  adapter_type: 'http'
  credential_ref?: string | null
  description?: string
  capabilities?: Capability[]
  timeout_seconds?: number
}

export interface PublishTargetVersionPayload {
  endpoint?: string
  credential_ref?: string | null
  capabilities?: Capability[]
  timeout_seconds?: number
}

export interface Run {
  id: string
  status: string
  parent_run_id: string | null
  root_run_id: string | null
  rerun_case_id: string | null
  snapshot: {
    target: {
      ref: { external_target_id: string; external_version_id: string }
      display_name: string
      adapter_type: string
    }
    dataset: DatasetVersion
    evaluator_specs: EvaluatorOption[]
    selected_case_ids: string[] | null
  }
}

// 便捷别名：Run 快照中的 target
export type RunTarget = Run['snapshot']['target']
