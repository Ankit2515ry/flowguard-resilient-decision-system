import { apiRequest, apiRequestWithResponse } from './client'
import type { RequestAccepted, RequestStatus } from '../types/request'
import type { RequestPayload } from '../types/workflow'
import type { AuditEvent, DecisionExplanation } from '../types/evidence'

export function submitRequest(payload: RequestPayload, idempotencyKey: string) {
  return apiRequestWithResponse<RequestAccepted>('/api/v1/requests', {
    method: 'POST',
    headers: { 'Idempotency-Key': idempotencyKey },
    body: payload,
  })
}

export function getRequest(requestId: string, signal?: AbortSignal) {
  return apiRequest<RequestStatus>(`/api/v1/requests/${encodeURIComponent(requestId)}`, { signal })
}

export function executeRequest(requestId: string) {
  return apiRequest<RequestStatus>(`/api/v1/requests/${encodeURIComponent(requestId)}/execute`, {
    method: 'POST',
  })
}

export function getRequestAudit(requestId: string, signal?: AbortSignal) {
  return apiRequest<AuditEvent[]>(`/api/v1/requests/${encodeURIComponent(requestId)}/audit`, { signal })
}

export function getRequestExplanation(requestId: string, signal?: AbortSignal) {
  return apiRequest<DecisionExplanation>(`/api/v1/requests/${encodeURIComponent(requestId)}/explanation`, { signal })
}
