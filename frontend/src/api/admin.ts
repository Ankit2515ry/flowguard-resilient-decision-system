import { apiRequest } from './client'
import type { ReviewItem, ReviewResolution, WorkflowActivation, WorkflowVersion } from '../types/admin'

function adminHeaders(token: string): HeadersInit {
  return { 'X-Admin-Token': token }
}

export function getReviews(token: string, signal?: AbortSignal) {
  return apiRequest<ReviewItem[]>('/api/v1/reviews', { headers: adminHeaders(token), signal })
}

export function resolveReview(requestId: string, token: string, action: 'APPROVE' | 'REJECT', reason: string) {
  return apiRequest<ReviewResolution>(`/api/v1/reviews/${encodeURIComponent(requestId)}/resolve`, {
    method: 'POST',
    headers: adminHeaders(token),
    body: { action, reason },
  })
}

export function getWorkflowVersions(workflowId: string, signal?: AbortSignal) {
  return apiRequest<WorkflowVersion[]>(`/api/v1/workflows/${encodeURIComponent(workflowId)}/versions`, { signal })
}

export function activateWorkflowVersion(workflowId: string, version: number, token: string) {
  return apiRequest<WorkflowActivation>('/api/v1/admin/workflows/activate', {
    method: 'POST',
    headers: adminHeaders(token),
    body: { workflow_id: workflowId, version },
  })
}
