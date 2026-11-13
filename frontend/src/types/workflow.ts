export interface WorkflowSummary {
  workflow_id: string
  active_version: number
  checksum: string
}

export interface RequestPayload {
  workflow_id: string
  data: Record<string, unknown>
}
