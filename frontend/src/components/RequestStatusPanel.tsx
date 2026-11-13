import { useState } from 'react'
import { AlertCircle, Check, CheckCircle2, Clock3, Copy, ExternalLink, LoaderCircle, RefreshCw, Zap } from 'lucide-react'
import { Link } from 'react-router-dom'
import { ApiError } from '../api/client'
import { executeRequest, getRequest } from '../api/requests'
import type { RequestAccepted, RequestStatus } from '../types/request'

function errorMessage(error: unknown) {
  if (!(error instanceof ApiError)) return 'The request could not be completed.'
  if (error.status === 0) return 'Could not reach the backend. Check that FlowGuard is running.'
  if (error.status === 404) return 'This request could not be found.'
  if (error.status === 409) return error.message || 'The request conflicts with its current state.'
  if (error.status === 422) return error.message || 'The backend rejected the request as invalid.'
  if (error.status >= 500) return 'The backend encountered an error. Refresh the status before deciding what to do next.'
  return error.message
}

export default function RequestStatusPanel({
  receipt,
  responseCode,
  initialStatus,
  onStatusChange,
}: {
  receipt: RequestAccepted
  responseCode?: number
  initialStatus?: RequestStatus
  onStatusChange?: (status: RequestStatus) => void
}) {
  const [status, setStatus] = useState<RequestStatus | undefined>(initialStatus)
  const [busy, setBusy] = useState<'refresh' | 'execute' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'error'>('idle')
  const displayStatus = status?.status ?? receipt.status

  async function copyRequestId() {
    try {
      await navigator.clipboard.writeText(receipt.request_id)
      setCopyState('copied')
      window.setTimeout(() => setCopyState('idle'), 1800)
    } catch {
      setCopyState('error')
    }
  }

  async function refreshStatus() {
    setBusy('refresh')
    setError(null)
    try {
      const current = await getRequest(receipt.request_id)
      setStatus(current)
      onStatusChange?.(current)
    } catch (cause) {
      setError(errorMessage(cause))
    } finally {
      setBusy(null)
    }
  }

  async function execute() {
    setBusy('execute')
    setError(null)
    try {
      const executed = await executeRequest(receipt.request_id)
      setStatus(executed)
      // Read persisted state after the explicit execution action.
      try {
        const current = await getRequest(receipt.request_id)
        setStatus(current)
        onStatusChange?.(current)
      } catch (cause) {
        onStatusChange?.(executed)
        throw cause
      }
    } catch (cause) {
      setError(errorMessage(cause))
    } finally {
      setBusy(null)
    }
  }

  return <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
    <div className="flex flex-col gap-3 border-b border-slate-100 bg-emerald-50/50 p-5 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3"><div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700"><CheckCircle2 size={19} /></div><div><h3 className="text-sm font-semibold text-slate-900">{responseCode === undefined ? 'Request status' : 'Request accepted'}</h3><p className="mt-1 text-xs leading-5 text-slate-600">{responseCode === 200 ? 'The backend returned the existing request for this idempotency key.' : responseCode === undefined ? 'This state is read from the backend.' : 'The backend accepted this request. Execution is a separate action.'}</p></div></div>
      {responseCode !== undefined && <span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600"><Clock3 size={13} /> HTTP {responseCode}{responseCode === 200 ? ' · replay' : responseCode === 202 ? ' · accepted' : ''}</span>}
    </div>
    <div className="grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-4">
      <div className="min-w-0"><p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">Request ID</p><div className="flex items-start gap-2"><p className="min-w-0 break-all font-mono text-xs text-slate-800">{receipt.request_id}</p><button type="button" onClick={() => void copyRequestId()} aria-label="Copy request ID" title="Copy request ID" className="shrink-0 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-indigo-600">{copyState === 'copied' ? <Check size={14} /> : <Copy size={14} />}</button></div>{copyState === 'copied' && <p role="status" className="mt-1 text-[10px] text-emerald-700">Request ID copied</p>}{copyState === 'error' && <p role="alert" className="mt-1 text-[10px] text-rose-700">Clipboard unavailable; select the ID to copy it.</p>}</div>
      <div><p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">Workflow</p><p className="text-sm font-medium text-slate-800">{receipt.workflow_id}</p></div>
      <div><p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">Pinned version</p><p className="text-sm font-medium text-slate-800">v{receipt.config_version}</p></div>
      <div><p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">Current status</p><span className="inline-flex rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700">{displayStatus}</span></div>
    </div>
    {status?.current_stage && <div className="border-t border-slate-100 px-5 py-3 text-xs text-slate-500">Current stage: <span className="font-medium text-slate-700">{status.current_stage}</span> <span className="px-1">·</span> Revision {status.revision}</div>}
    {status?.decision && <div className="border-t border-slate-100 px-5 py-3 text-sm text-slate-700">Decision: <strong>{status.decision.outcome}</strong></div>}
    {error && <div role="alert" className="mx-5 mb-4 flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs leading-5 text-rose-800"><AlertCircle size={15} className="mt-0.5 shrink-0" />{error}</div>}
    <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 bg-slate-50/70 p-4">
      <button type="button" onClick={execute} disabled={busy !== null || displayStatus !== 'RECEIVED'} className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"><Zap size={14} />{busy === 'execute' ? 'Executing…' : 'Execute workflow'}</button>
      <button type="button" onClick={refreshStatus} disabled={busy !== null} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50">{busy === 'refresh' ? <LoaderCircle size={14} className="animate-spin" /> : <RefreshCw size={14} />}Refresh status</button>
      <Link to={`/requests?request_id=${encodeURIComponent(receipt.request_id)}`} className="ml-auto inline-flex items-center gap-1.5 px-2 py-2 text-xs font-semibold text-indigo-600 hover:text-indigo-700">Open request details <ExternalLink size={13} /></Link>
    </div>
  </section>
}
