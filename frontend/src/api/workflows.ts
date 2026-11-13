import { apiRequest } from './client'
import type { WorkflowSummary } from '../types/workflow'

export function getWorkflows(signal?: AbortSignal) {
  return apiRequest<WorkflowSummary[]>('/api/v1/workflows', { signal })
}
