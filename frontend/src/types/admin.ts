export interface ReviewItem {
  request_id: string
  workflow_id: string
  config_version: number
  status: string
  current_stage: string
  created_at: string
}

export interface ReviewResolution {
  request_id: string
  status: string
  decision_outcome: string
  replayed: boolean
}

export interface WorkflowVersion {
  workflow_id: string
  version: number
  checksum: string
  is_active: boolean
}

export interface WorkflowActivation {
  workflow_id: string
  active_version: number
  changed: boolean
}
