import { useEffect, useState } from 'react'
import { AlertCircle, FilePlus2, LoaderCircle, ShieldCheck, TriangleAlert } from 'lucide-react'
import { ApiError } from '../api/client'
import { submitRequest } from '../api/requests'
import { getWorkflows } from '../api/workflows'
import EmptyState from '../components/EmptyState'
import PageHeading from '../components/PageHeading'
import RequestStatusPanel from '../components/RequestStatusPanel'
import type { RequestAccepted } from '../types/request'
import type { RequestPayload, WorkflowSummary } from '../types/workflow'

interface SubmissionAttempt {
  key: string
  payload: RequestPayload
}

function SubmissionError({ error }: { error: ApiError }) {
  const known = error.status === 409 || error.status === 422
  const heading = error.status === 409 ? 'Idempotency conflict' : error.status === 422 ? 'Request validation failed' : error.status === 404 ? 'Workflow unavailable' : error.status >= 500 ? 'Backend error' : error.status === 0 ? 'Connection error' : 'Request failed'
  const details = Array.isArray(error.details) ? error.details : null
  return <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
    <div className="flex items-start gap-2"><AlertCircle size={17} className="mt-0.5 shrink-0 text-rose-600" /><div><p className="font-semibold">{heading}</p><p className="mt-1 leading-6">{error.message}</p>
      {details && <ul className="mt-2 list-inside list-disc space-y-1 text-xs">{details.map((item, index) => <li key={index}>{typeof item === 'object' && item !== null && 'message' in item ? String(item.message) : JSON.stringify(item)}</li>)}</ul>}
      {error.status >= 500 && <p className="mt-2 text-xs">The response may be uncertain. If the server accepted the request, retry with the same idempotency key.</p>}
      {known && <p className="mt-2 text-xs">Correct the request and submit again; a new logical submission will use a new key.</p>}
    </div></div>
  </div>
}

export default function SubmitRequestPage() {
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([])
  const [workflowsLoading, setWorkflowsLoading] = useState(true)
  const [workflowsError, setWorkflowsError] = useState<string | null>(null)
  const [workflowId, setWorkflowId] = useState('')
  const [age, setAge] = useState('')
  const [income, setIncome] = useState('')
  const [creditScore, setCreditScore] = useState('')
  const [registrationStatus, setRegistrationStatus] = useState('')
  const [taxClearance, setTaxClearance] = useState('')
  const [sanctionsClear, setSanctionsClear] = useState('')
  const [turnover, setTurnover] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [uncertainAttempt, setUncertainAttempt] = useState<SubmissionAttempt | null>(null)
  const [receipt, setReceipt] = useState<RequestAccepted | null>(null)
  const [responseCode, setResponseCode] = useState<number>()

  useEffect(() => {
    const controller = new AbortController()
    getWorkflows(controller.signal)
      .then((items) => {
        setWorkflows(items)
        setWorkflowId((current) => current || items.find((item) => ['loan_approval', 'vendor_approval'].includes(item.workflow_id))?.workflow_id || '')
      })
      .catch((cause: unknown) => {
        if (!(cause instanceof DOMException && cause.name === 'AbortError')) {
          setWorkflowsError(cause instanceof Error ? cause.message : 'Could not load workflows.')
        }
      })
      .finally(() => setWorkflowsLoading(false))
    return () => controller.abort()
  }, [])

  const hasSelectedWorkflow = workflows.some((workflow) => workflow.workflow_id === workflowId)
  const supported = workflowId === 'loan_approval' || workflowId === 'vendor_approval'

  function makePayload(): RequestPayload {
    if (workflowId === 'loan_approval') {
      return { workflow_id: workflowId, data: { applicant: { age: Number(age), monthly_income: Number(income), credit_score: Number(creditScore) } } }
    }
    return { workflow_id: workflowId, data: { vendor: { registration_status: registrationStatus, compliance: { tax_clearance: taxClearance === 'true', sanctions_clear: sanctionsClear === 'true' }, annual_turnover: Number(turnover) } } }
  }

  async function sendAttempt(attempt: SubmissionAttempt) {
    setSubmitting(true)
    setError(null)
    setReceipt(null)
    try {
      const result = await submitRequest(attempt.payload, attempt.key)
      setReceipt(result.data)
      setResponseCode(result.status)
      setUncertainAttempt(null)
    } catch (cause) {
      const apiError = cause instanceof ApiError ? cause : new ApiError('The request could not be completed.', 0)
      setError(apiError)
      setUncertainAttempt(apiError.status === 0 || apiError.status >= 500 ? attempt : null)
    } finally {
      setSubmitting(false)
    }
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setReceipt(null)
    setResponseCode(undefined)
    setUncertainAttempt(null)
    setError(null)
    const attempt = { key: crypto.randomUUID(), payload: makePayload() }
    void sendAttempt(attempt)
  }

  return <>
    <PageHeading eyebrow="Intake" title="Submit a request" description="Send a request to a discovered workflow. The backend validates the payload and selects the pinned configuration version; execution remains a separate action." />
    {workflowsLoading ? <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-600"><LoaderCircle size={17} className="animate-spin text-indigo-600" /> Loading available workflows…</div>
      : workflowsError ? <div role="alert" className="mb-5 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"><AlertCircle size={17} className="mt-0.5 shrink-0" />Could not load workflows: {workflowsError}</div>
        : workflows.length === 0 ? <EmptyState icon={FilePlus2} title="No workflows are available" description="The backend returned no active workflows. Start FlowGuard with its validated workflow configurations to submit requests." />
          : <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(300px,0.75fr)]">
            <form onSubmit={handleSubmit} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
              <div className="mb-5"><label htmlFor="workflow" className="mb-2 block text-xs font-semibold text-slate-700">Workflow</label><select id="workflow" required value={workflowId} onChange={(event) => { setWorkflowId(event.target.value); setError(null); setReceipt(null) }} className="form-control"><option value="" disabled>Select an available workflow</option>{workflows.map((item) => <option key={item.workflow_id} value={item.workflow_id}>{item.workflow_id} · active v{item.active_version}</option>)}</select><p className="mt-1.5 text-xs text-slate-500">Active version is selected by the backend when the request is accepted.</p></div>
              {!hasSelectedWorkflow ? <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">Select an active workflow to continue.</div>
                : !supported ? <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900"><TriangleAlert size={17} className="mt-0.5 shrink-0" /><p>This workflow is available in the backend, but its input schema is not one of the loan/vendor schemas supported by this form.</p></div>
                  : workflowId === 'loan_approval' ? <fieldset className="space-y-4"><legend className="mb-4 text-sm font-semibold text-slate-900">Applicant information</legend><div className="grid gap-4 sm:grid-cols-2"><label className="field-label">Age<input className="form-control mt-2" type="number" step="1" required value={age} onChange={(event) => setAge(event.target.value)} /></label><label className="field-label">Monthly income<input className="form-control mt-2" type="number" step="any" required value={income} onChange={(event) => setIncome(event.target.value)} /></label><label className="field-label sm:col-span-2">Credit score<input className="form-control mt-2 max-w-[240px]" type="number" step="1" required value={creditScore} onChange={(event) => setCreditScore(event.target.value)} /></label></div></fieldset>
                    : <fieldset className="space-y-4"><legend className="mb-4 text-sm font-semibold text-slate-900">Vendor information</legend><label className="field-label">Registration status<input className="form-control mt-2" type="text" required value={registrationStatus} onChange={(event) => setRegistrationStatus(event.target.value)} /></label><div className="grid gap-4 sm:grid-cols-2"><label className="field-label">Tax clearance<select className="form-control mt-2" required value={taxClearance} onChange={(event) => setTaxClearance(event.target.value)}><option value="" disabled>Select a value</option><option value="true">True</option><option value="false">False</option></select></label><label className="field-label">Sanctions clear<select className="form-control mt-2" required value={sanctionsClear} onChange={(event) => setSanctionsClear(event.target.value)}><option value="" disabled>Select a value</option><option value="true">True</option><option value="false">False</option></select></label></div><label className="field-label">Annual turnover<input className="form-control mt-2" type="number" step="any" required value={turnover} onChange={(event) => setTurnover(event.target.value)} /></label></fieldset>}
              {error && <div className="mt-5"><SubmissionError error={error} /></div>}
              {uncertainAttempt && <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4"><div className="flex items-start gap-2 text-sm leading-5 text-amber-950"><TriangleAlert size={16} className="mt-0.5 shrink-0 text-amber-600" /><p>The server may have accepted the prior submission. Retry that exact payload with its original key, or refresh the request later using its ID if available.</p></div><button type="button" disabled={submitting} onClick={() => void sendAttempt(uncertainAttempt)} className="mt-3 rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs font-semibold text-amber-900 hover:bg-amber-100 disabled:opacity-50">{submitting ? 'Retrying…' : 'Retry same submission'}</button></div>}
              <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-slate-100 pt-5"><button type="submit" disabled={submitting || !supported || !hasSelectedWorkflow} className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50">{submitting && !uncertainAttempt ? <LoaderCircle size={16} className="animate-spin" /> : <FilePlus2 size={16} />}{submitting ? 'Submitting…' : 'Submit request'}</button><span className="inline-flex items-center gap-1.5 text-xs text-slate-400"><ShieldCheck size={14} /> Eligibility and decisions stay in the backend</span></div>
            </form>
            <div className="space-y-4"><div className="rounded-xl border border-indigo-100 bg-indigo-50/60 p-5"><h3 className="text-sm font-semibold text-slate-900">What happens next</h3><ol className="mt-4 space-y-3 text-xs leading-5 text-slate-600"><li className="flex gap-3"><span className="step-dot">1</span><span>FlowGuard validates the input schema and accepts the request.</span></li><li className="flex gap-3"><span className="step-dot">2</span><span>The response includes a request ID and pinned workflow version.</span></li><li className="flex gap-3"><span className="step-dot">3</span><span>You explicitly choose whether to execute the accepted request.</span></li></ol></div><div className="rounded-xl border border-slate-200 bg-white p-5"><h3 className="text-sm font-semibold text-slate-900">Idempotent submission</h3><p className="mt-2 text-xs leading-5 text-slate-500">Each new submission uses a UUID idempotency key. If the network or server response is uncertain, the retry button reuses that key and the exact same payload. No automatic resubmissions occur.</p></div></div>
          </div>}
    {receipt && <div className="mt-6"><RequestStatusPanel receipt={receipt} responseCode={responseCode} /></div>}
  </>
}
