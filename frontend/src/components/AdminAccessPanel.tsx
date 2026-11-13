import { useState, type FormEvent } from 'react'
import { KeyRound, LockKeyhole, LogOut, ShieldCheck } from 'lucide-react'
import { useAdminSession } from '../auth/adminSessionContext'

export default function AdminAccessPanel({ onDisconnect, disabled = false }: { onDisconnect?: () => void; disabled?: boolean }) {
  const { token, setToken, clearToken } = useAdminSession()
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)

  function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const value = draft.trim()
    if (!value) {
      setError('Enter the admin token configured for the backend.')
      return
    }
    setToken(value)
    setDraft('')
    setError(null)
  }

  return <section className="mb-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center"><div className="flex items-start gap-3"><div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${token ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>{token ? <ShieldCheck size={19} /> : <LockKeyhole size={19} />}</div><div><h3 className="text-sm font-semibold text-slate-900">{token ? 'Admin token entered for this tab' : 'Admin access required'}</h3><p className="mt-1 max-w-xl text-xs leading-5 text-slate-500">Enter the server-configured demo token to use protected operations. It stays in React memory and is cleared when you reload or disconnect.</p></div></div>
      {token ? <button type="button" disabled={disabled} onClick={() => { onDisconnect?.(); clearToken() }} className="inline-flex w-fit items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50"><LogOut size={14} />Forget token</button> : <form onSubmit={connect} className="flex w-full gap-2 sm:w-auto"><label htmlFor="admin-token" className="sr-only">Admin token</label><input id="admin-token" type="password" autoComplete="off" value={draft} onChange={(event) => { setDraft(event.target.value); setError(null) }} placeholder="Enter admin token" className="form-control min-w-0 sm:w-64" /><button type="submit" className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800"><KeyRound size={14} />Connect</button></form>}
    </div>
    {error && <p role="alert" className="mt-3 text-xs text-rose-700">{error}</p>}
  </section>
}
