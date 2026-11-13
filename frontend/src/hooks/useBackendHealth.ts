import { useCallback, useEffect, useState } from 'react'
import { getHealth } from '../api/health'

export type BackendState = 'checking' | 'connected' | 'disconnected'

export function useBackendHealth() {
  const [state, setState] = useState<BackendState>('checking')
  const [check, setCheck] = useState(0)
  const refresh = useCallback(() => setCheck((value) => value + 1), [])

  useEffect(() => {
    const controller = new AbortController()
    getHealth(controller.signal)
      .then((result) => setState(result.status === 'ok' ? 'connected' : 'disconnected'))
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
          setState('disconnected')
        }
      })
    return () => controller.abort()
  }, [check])

  return { state, refresh }
}
