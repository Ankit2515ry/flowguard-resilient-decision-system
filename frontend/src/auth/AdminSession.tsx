import { useMemo, useState, type ReactNode } from 'react'
import { AdminSessionContext, type AdminSessionValue } from './adminSessionContext'

export function AdminSessionProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(null)
  const value = useMemo<AdminSessionValue>(() => ({
    token,
    setToken: (nextToken) => setTokenState(nextToken),
    clearToken: () => setTokenState(null),
  }), [token])

  return <AdminSessionContext.Provider value={value}>{children}</AdminSessionContext.Provider>
}
