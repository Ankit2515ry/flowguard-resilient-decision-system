import type { ApiErrorEnvelope } from '../types/api'

const configuredOrigin = import.meta.env.VITE_API_BASE_URL?.trim() ?? ''
export const API_BASE_URL = configuredOrigin.replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number
  readonly code?: string
  readonly details?: unknown

  constructor(message: string, status: number, code?: string, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

export interface RequestOptions {
  headers?: HeadersInit
  signal?: AbortSignal
}

export interface ApiResponse<T> {
  data: T
  status: number
  headers: Headers
}

export async function apiRequestWithResponse<T>(
  path: string,
  options: RequestOptions & { method?: string; body?: unknown } = {},
): Promise<ApiResponse<T>> {
  const headers = new Headers(options.headers)
  if (options.body !== undefined) headers.set('Content-Type', 'application/json')

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method ?? 'GET',
      headers,
      signal: options.signal,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError('Could not reach the FlowGuard backend.', 0)
  }

  const contentType = response.headers.get('content-type') ?? ''
  const payload: unknown = contentType.includes('application/json')
    ? await response.json().catch(() => undefined)
    : await response.text().catch(() => '')

  if (!response.ok) {
    const envelope = payload as ApiErrorEnvelope | undefined
    throw new ApiError(
      envelope?.error?.message || response.statusText || 'The request failed.',
      response.status,
      envelope?.error?.code,
      envelope?.error?.details,
    )
  }

  return { data: payload as T, status: response.status, headers: response.headers }
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions & { method?: string; body?: unknown } = {},
): Promise<T> {
  const result = await apiRequestWithResponse<T>(path, options)
  return result.data
}
