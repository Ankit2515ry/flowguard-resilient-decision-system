export interface AuditEvent {
  sequence: number
  event_type: string
  old_state: string | null
  new_state: string
  stage: string | null
  created_at: string
  config_version: number
  details: Record<string, unknown>
}

export interface RuleTrace {
  rule_id: string
  expression_reference: string
  operator: string
  actual_value: unknown
  expected_value: unknown
  passed: boolean
  failure_action: string
  reason: string
  config_version: number
}

export interface StageResult {
  stage_id?: string
  event?: string
  outcome?: string | null
  config_version?: number
}

export interface ExternalResult {
  stage_id: string
  operation: string
  operation_key: string
  attempt: number
  success: boolean
  retryable: boolean
  category: string
  message: string
  config_version: number
}

export interface DecisionExplanation {
  request_id: string
  workflow_id: string
  config_version: number
  status: string
  decision_outcome: string | null
  pending: boolean
  summary: string
  rule_traces: RuleTrace[]
  stage_results: StageResult[]
  external_results: ExternalResult[]
  review_resolution: Record<string, unknown> | null
}
