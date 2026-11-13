import { useState } from 'react'
import { AlertCircle, CheckCircle2, ClipboardCheck, LoaderCircle, RefreshCw, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getReviews, resolveReview } from '../api/admin'
import { ApiError } from '../api/client'
import { useAdminSession } from '../auth/adminSessionContext'
import AdminAccessPanel from '../components/AdminAccessPanel'
import EmptyState from '../components/EmptyState'
import PageHeading from '../components/PageHeading'
import type { ReviewItem } from '../types/admin'
import type { FormEvent } from 'react'

function adminError(error: unknown) {
  if (!(error instanceof ApiError)) return 'Could not complete the admin request.'
  if (error.status === 0) return 'Could not reach the backend. Check that FlowGuard is running.'
  if (error.status === 401) return 'The backend requires an X-Admin-Token header. Enter the configured token and retry.'
  if (error.status === 403) return '403 Forbidden: the backend rejected this admin token. Forget it and enter the correct server-configured token.'
  if (error.status === 409) return '409 Conflict: this review changed or was resolved elsewhere. Refresh the queue before taking another action.'
  if (error.status === 503) return 'Admin authentication is not configured on the backend.'
  return error.message
}

function ReviewCard({ item, busy, onResolve }: { item: ReviewItem; busy: boolean; onResolve: (item: ReviewItem, action: 'APPROVE' | 'REJECT', reason: string) => Promise<void> }) {
  const [action, setAction] = useState<'APPROVE' | 'REJECT'>('APPROVE')
  const [reason, setReason] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalizedReason = reason.trim()
    if (!normalizedReason) {
      setFormError('A nonblank reason is required.')
      return
    }
    if (normalizedReason.length > 2000) {
      setFormError('The reason must be 2000 characters or fewer.')
      return
    }
    setFormError(null)
    await onResolve(item, action, normalizedReason)
  }

  return <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
    <div className="flex flex-col justify-between gap-3 border-b border-slate-100 pb-4 sm:flex-row sm:items-start"><div><div className="flex items-center gap-2"><span className="rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-semibold text-amber-800">{item.status}</span><span className="text-xs text-slate-400">{item.workflow_id} · v{item.config_version}</span></div><p className="mt-3 text-xs font-medium uppercase tracking-wide text-slate-400">Request ID</p><p className="mt-1 break-all font-mono text-xs text-slate-700">{item.request_id}</p></div><div className="text-left text-xs leading-5 text-slate-500 sm:text-right"><p>Stage <span className="font-semibold text-slate-700">{item.current_stage}</span></p><Link to={`/requests?request_id=${encodeURIComponent(item.request_id)}`} className="mt-1 inline-block font-semibold text-indigo-600 hover:text-indigo-700">Open request details</Link></div></div>
    <form onSubmit={submit} className="mt-4 grid gap-4 md:grid-cols-[minmax(170px,0.4fr)_minmax(0,1fr)_auto] md:items-end">
      <label className="field-label">Review action<select value={action} onChange={(event) => setAction(event.target.value as 'APPROVE' | 'REJECT')} className="form-control mt-2"><option value="APPROVE">Approve</option><option value="REJECT">Reject</option></select></label>
      <label className="field-label">Reason <span className="font-normal text-slate-400">(required)</span><textarea required maxLength={2000} rows={2} value={reason} onChange={(event) => { setReason(event.target.value); setFormError(null) }} placeholder="Record the reason for this decision" className="form-control mt-2 min-h-20 resize-y" /></label>
      <button type="submit" disabled={busy} className="inline-flex h-[42px] items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">{busy ? <LoaderCircle size={15} className="animate-spin" /> : <ClipboardCheck size={15} />}{busy ? 'Resolving…' : 'Resolve review'}</button>
    </form>
    {formError && <p role="alert" className="mt-2 text-xs text-rose-700">{formError}</p>}
  </article>
}

export default function ManualReviewsPage() {
  const { token } = useAdminSession()
  const [reviews, setReviews] = useState<ReviewItem[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  async function refreshQueue() {
    if (!token) return
    setLoading(true)
    setError(null)
    setSuccess(null)
    try {
      setReviews(await getReviews(token))
    } catch (cause) {
      if (cause instanceof ApiError && (cause.status === 403 || cause.status === 409)) setReviews(null)
      setError(adminError(cause))
    } finally {
      setLoading(false)
    }
  }

  async function handleResolve(item: ReviewItem, action: 'APPROVE' | 'REJECT', reason: string) {
    if (!token) return
    const verb = action === 'APPROVE' ? 'approve' : 'reject'
    const confirmed = window.confirm(`Confirm ${verb} for request ${item.request_id}?\n\nReason: ${reason}`)
    if (!confirmed) return
    setBusyId(item.request_id)
    setError(null)
    setSuccess(null)
    try {
      const result = await resolveReview(item.request_id, token, action, reason)
      setSuccess(result.replayed ? `This review was already resolved as ${result.decision_outcome}.` : `Review resolved as ${result.decision_outcome}.`)
      setReviews(null)
      setLoading(true)
      try {
        setReviews(await getReviews(token))
      } catch (cause) {
        setError(adminError(cause))
      } finally {
        setLoading(false)
      }
    } catch (cause) {
      if (cause instanceof ApiError && (cause.status === 403 || cause.status === 409)) setReviews(null)
      setError(adminError(cause))
    } finally {
      setBusyId(null)
    }
  }

  return <>
    <PageHeading eyebrow="Operations" title="Manual reviews" description="Resolve requests that the configured backend workflow has routed for human review. Each resolution and reason is recorded by FlowGuard." />
    <AdminAccessPanel disabled={loading || busyId !== null} onDisconnect={() => { setReviews(null); setError(null); setSuccess(null) }} />
    {error && <div role="alert" className="mb-4 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm leading-6 text-rose-800"><AlertCircle size={17} className="mt-1 shrink-0" /><div><p className="font-semibold">{error.includes('token') || error.includes('X-Admin-Token') || error.includes('authentication') ? 'Admin access error' : error.includes('changed or was resolved') ? 'Review conflict (409)' : 'Request error'}</p><p>{error}</p></div></div>}
    {success && <div role="status" className="mb-4 flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800"><CheckCircle2 size={17} />{success}</div>}
    {!token ? <EmptyState icon={ShieldCheck} title="Connect admin access to view reviews" description="The review queue requires the server-configured X-Admin-Token. The token is held in memory for this tab only." />
      : <><div className="mb-4 flex items-center justify-between gap-3"><p className="text-xs text-slate-500">Queue contents are returned by the authenticated backend.</p><button type="button" onClick={() => void refreshQueue()} disabled={loading || busyId !== null} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50">{loading ? <LoaderCircle size={14} className="animate-spin" /> : <RefreshCw size={14} />}{loading ? 'Loading…' : 'Refresh queue'}</button></div>
        {reviews === null && !loading ? <EmptyState icon={ShieldCheck} title="Load the review queue" description="Use Refresh queue to request pending reviews from the backend." /> : null}
        {loading && reviews === null ? <div className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-500">Loading pending reviews…</div> : null}
        {reviews && reviews.length === 0 && !loading ? <EmptyState icon={ShieldCheck} title="No pending reviews" description="The backend currently returned an empty manual review queue." /> : null}
        {reviews && reviews.length > 0 && <div className="space-y-4">{reviews.map((item) => <ReviewCard key={item.request_id} item={item} busy={busyId === item.request_id} onResolve={handleResolve} />)}</div>}
      </>}
  </>
}
