import { useState, type FormEvent } from 'react'
import { AlertCircle, ClipboardList, LoaderCircle, Search } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { getRequest, getRequestAudit, getRequestExplanation } from '../api/requests'
import AuditTimeline from '../components/AuditTimeline'
import DecisionEvidence from '../components/DecisionEvidence'
import EmptyState from '../components/EmptyState'
import PageHeading from '../components/PageHeading'
import RequestStatusPanel from '../components/RequestStatusPanel'
import type { RequestAccepted, RequestStatus } from '../types/request'
import type { AuditEvent, DecisionExplanation } from '../types/evidence'

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function asReceipt(status: RequestStatus): RequestAccepted {
  return {
    request_id: status.request_id,
    status: status.status,
    workflow_id: status.workflow_id,
    config_version: status.config_version,
    status_url: `/api/v1/requests/${status.request_id}`,
  }
}

export default function RequestDetailsPage() {
  const [searchParams] = useSearchParams()
  const [requestId, setRequestId] = useState(searchParams.get('request_id') ?? '')
  const [status, setStatus] = useState<RequestStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [audit, setAudit] = useState<AuditEvent[] | null>(null)
  const [auditError, setAuditError] = useState<string | null>(null)
  const [explanation, setExplanation] = useState<DecisionExplanation | null>(null)
  const [explanationError, setExplanationError] = useState<string | null>(null)
  const [evidenceLoading, setEvidenceLoading] = useState(false)

  async function loadEvidence(id: string) {
    setEvidenceLoading(true)
    setAudit(null)
    setExplanation(null)
    setAuditError(null)
    setExplanationError(null)
    const [auditResult, explanationResult] = await Promise.allSettled([
      getRequestAudit(id),
      getRequestExplanation(id),
    ])
    if (auditResult.status === 'fulfilled') setAudit(auditResult.value)
    else setAuditError(auditResult.reason instanceof Error ? auditResult.reason.message : 'Could not load audit history.')
    if (explanationResult.status === 'fulfilled') setExplanation(explanationResult.value)
    else setExplanationError(explanationResult.reason instanceof Error ? explanationResult.reason.message : 'Could not load the decision explanation.')
    setEvidenceLoading(false)
  }

  async function lookup(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault()
    const normalized = requestId.trim()
    setStatus(null)
    setAudit(null)
    setExplanation(null)
    setError(null)
    if (!uuidPattern.test(normalized)) {
      setError('Enter a valid request UUID.')
      return
    }
    setLoading(true)
    try {
      const current = await getRequest(normalized)
      setStatus(current)
      await loadEvidence(normalized)
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 404) setError('No request was found for that UUID.')
      else if (cause instanceof ApiError && cause.status === 0) setError('Could not reach the backend. Check that FlowGuard is running.')
      else if (cause instanceof ApiError && cause.status >= 500) setError('The backend could not retrieve this request. Try again later.')
      else setError(cause instanceof Error ? cause.message : 'Could not retrieve the request.')
    } finally {
      setLoading(false)
    }
  }

  return <>
    <PageHeading eyebrow="Requests" title="Request details" description="Look up a request using its UUID to view persisted status, pinned version, and backend decision state." />
    <form onSubmit={lookup} className="mb-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <label htmlFor="request-id" className="mb-2 block text-xs font-semibold text-slate-700">Request UUID</label>
      <div className="flex flex-col gap-3 sm:flex-row"><input id="request-id" type="text" autoComplete="off" spellCheck={false} placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" value={requestId} onChange={(event) => setRequestId(event.target.value)} className="form-control min-w-0 flex-1 font-mono text-xs" /><button type="submit" disabled={loading || !requestId.trim()} className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50">{loading ? <LoaderCircle size={16} className="animate-spin" /> : <Search size={16} />}{loading ? 'Looking up…' : 'Look up request'}</button></div>
      <p className="mt-2 text-xs text-slate-500">Request history cannot be searched because the backend has no request-list endpoint.</p>
    </form>
    {error && <div role="alert" className="mb-5 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"><AlertCircle size={17} className="mt-0.5 shrink-0" />{error}</div>}
    {status && <div className="space-y-6">
      <RequestStatusPanel receipt={asReceipt(status)} initialStatus={status} onStatusChange={(nextStatus) => { setStatus(nextStatus); void loadEvidence(nextStatus.request_id) }} />
      <section><div className="mb-3 flex items-end justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">Request history</p><h3 className="mt-1 text-base font-semibold text-slate-900">Persisted audit timeline</h3></div><p className="text-right text-[11px] text-slate-400">Ordered by audit sequence</p></div>{evidenceLoading ? <div className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-500">Loading audit history…</div> : auditError ? <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">Could not load audit events: {auditError}</div> : audit ? <AuditTimeline events={audit} /> : null}</section>
      <section><div className="mb-3"><p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">Decision evidence</p><h3 className="mt-1 text-base font-semibold text-slate-900">Stored explanation and verification</h3></div>{evidenceLoading ? <div className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-500">Loading explanation…</div> : explanationError ? <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">Could not load explanation: {explanationError}</div> : explanation ? <DecisionEvidence explanation={explanation} /> : null}</section>
    </div>}
    {!status && !error && !loading && <EmptyState icon={ClipboardList} title="No request selected" description="Enter a request UUID above to retrieve its current persisted state." />}
  </>
}
