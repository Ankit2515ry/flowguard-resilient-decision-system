export interface RequestAccepted {
  request_id: string
  status: string
  workflow_id: string
  config_version: number
  status_url: string
}

export interface DecisionView {
  outcome: string
  explanation: Record<string, unknown>
  created_at: string
}

export interface RequestStatus {
  request_id: string
  status: string
  workflow_id: string
  config_version: number
  current_stage: string | null
  revision: number
  created_at: string
  updated_at: string
  decision: DecisionView | null
}
