import { createContext, useContext } from 'react'

export interface AdminSessionValue {
  token: string | null
  setToken: (token: string) => void
  clearToken: () => void
}

export const AdminSessionContext = createContext<AdminSessionValue | null>(null)

export function useAdminSession() {
  const value = useContext(AdminSessionContext)
  if (!value) throw new Error('useAdminSession must be used inside AdminSessionProvider')
  return value
}
