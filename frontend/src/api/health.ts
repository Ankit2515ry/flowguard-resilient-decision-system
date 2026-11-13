import { apiRequest } from './client'
import type { HealthResponse } from '../types/api'

export function getHealth(signal?: AbortSignal) {
  return apiRequest<HealthResponse>('/health', { signal })
}
