export interface HealthResponse {
  status: string
}

export interface ApiErrorEnvelope {
  error?: {
    code?: string
    message?: string
    details?: unknown
  }
}
