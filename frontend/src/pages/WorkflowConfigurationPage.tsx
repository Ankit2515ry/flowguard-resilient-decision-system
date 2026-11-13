import { useEffect, useState } from 'react'
import { AlertCircle, CheckCircle2, GitBranch, LoaderCircle, LockKeyhole, RefreshCw, ShieldCheck } from 'lucide-react'
import { activateWorkflowVersion, getWorkflowVersions } from '../api/admin'
import { getWorkflows } from '../api/workflows'
import { ApiError } from '../api/client'
import { useAdminSession } from '../auth/adminSessionContext'
import AdminAccessPanel from '../components/AdminAccessPanel'
import EmptyState from '../components/EmptyState'
import PageHeading from '../components/PageHeading'
import type { WorkflowVersion } from '../types/admin'
import type { WorkflowSummary } from '../types/workflow'

function adminError(error: unknown) {
  if (!(error instanceof ApiError)) return 'Could not complete the request.'
  if (error.status === 0) return 'Could not reach the backend. Check that FlowGuard is running.'
  if (error.status === 401) return 'The backend requires an X-Admin-Token header.'
  if (error.status === 403) return '403 Forbidden: the backend rejected this admin token. Forget it and enter the correct server-configured token.'
  if (error.status === 409) return '409 Conflict: workflow state changed before activation. Refresh the workflow versions and try again.'
  if (error.status === 503) return 'Admin authentication is not configured on the backend.'
  return error.message
}

export default function WorkflowConfigurationPage() {
  const { token } = useAdminSession()
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([])
  const [workflowsLoading, setWorkflowsLoading] = useState(true)
  const [workflowsError, setWorkflowsError] = useState<string | null>(null)
  const [workflowId, setWorkflowId] = useState('')
  const [versions, setVersions] = useState<WorkflowVersion[] | null>(null)
  const [versionsLoading, setVersionsLoading] = useState(false)
  const [versionsError, setVersionsError] = useState<string | null>(null)
  const [activationError, setActivationError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [activatingVersion, setActivatingVersion] = useState<number | null>(null)

  async function loadVersions(id: string) {
    setVersionsLoading(true)
    setVersions(null)
    setVersionsError(null)
    try {
      setVersions(await getWorkflowVersions(id))
    } catch (cause) {
      setVersionsError(cause instanceof Error ? cause.message : 'Could not load workflow versions.')
    } finally {
      setVersionsLoading(false)
    }
  }

  async function loadWorkflows() {
    setWorkflowsLoading(true)
    setWorkflowsError(null)
    try {
      const items = await getWorkflows()
      setWorkflows(items)
      const selected = items.find((item) => item.workflow_id === workflowId) ?? items[0]
      if (selected) {
        setWorkflowId(selected.workflow_id)
        await loadVersions(selected.workflow_id)
      } else {
        setWorkflowId('')
        setVersions([])
      }
    } catch (cause) {
      setWorkflowsError(cause instanceof Error ? cause.message : 'Could not load workflows.')
    } finally {
      setWorkflowsLoading(false)
    }
  }

  useEffect(() => {
    void loadWorkflows()
  // Load public workflow discovery once when the page opens.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function activate(version: WorkflowVersion) {
    if (!token) return
    const confirmed = window.confirm(
      `Activate ${version.workflow_id} version ${version.version}?\n\nNew requests will use the selected version. Existing requests retain their pinned config version.`,
    )
    if (!confirmed) return
    setActivatingVersion(version.version)
    setActivationError(null)
    setSuccess(null)
    try {
      const result = await activateWorkflowVersion(version.workflow_id, version.version, token)
      setSuccess(result.changed
        ? `${result.workflow_id} is now active at version ${result.active_version}. Existing requests retain their pinned config version.`
        : `${result.workflow_id} version ${result.active_version} was already active.`)
      await loadWorkflows()
    } catch (cause) {
      setActivationError(adminError(cause))
      if (cause instanceof ApiError && cause.status === 409) await loadWorkflows()
    } finally {
      setActivatingVersion(null)
    }
  }

  const activeVersion = versions?.find((version) => version.is_active)?.version

  return <>
    <PageHeading eyebrow="Configuration" title="Workflow configuration" description="Inspect persisted workflow versions and explicitly activate a version for new requests." />
    <AdminAccessPanel />
    <div className="mb-6 flex items-start gap-3 rounded-xl border border-blue-100 bg-blue-50/70 p-4 text-sm leading-6 text-blue-900"><GitBranch size={18} className="mt-0.5 shrink-0 text-blue-600" /><p>Activation affects new requests only. Existing requests keep the configuration version pinned when they were accepted.</p></div>
    {activationError && <div role="alert" className="mb-4 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm leading-6 text-rose-800"><AlertCircle size={17} className="mt-1 shrink-0" /><div><p className="font-semibold">{activationError.includes('rejected') || activationError.includes('requires') || activationError.includes('authentication') ? 'Admin access error' : activationError.includes('changed before') ? 'Activation conflict (409)' : 'Activation error'}</p><p>{activationError}</p></div></div>}
    {success && <div role="status" className="mb-4 flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800"><CheckCircle2 size={17} />{success}</div>}
    {workflowsError && <div role="alert" className="mb-4 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">Could not load workflows: {workflowsError}</div>}
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div className="min-w-0 flex-1"><label htmlFor="workflow-select" className="mb-2 block text-xs font-semibold text-slate-700">Workflow</label><select id="workflow-select" value={workflowId} disabled={workflowsLoading || workflows.length === 0} onChange={(event) => { setWorkflowId(event.target.value); setSuccess(null); setActivationError(null); void loadVersions(event.target.value) }} className="form-control sm:max-w-md"><option value="" disabled>Select a workflow</option>{workflows.map((workflow) => <option key={workflow.workflow_id} value={workflow.workflow_id}>{workflow.workflow_id} · active v{workflow.active_version}</option>)}</select></div><button type="button" onClick={() => void loadWorkflows()} disabled={workflowsLoading || activatingVersion !== null} className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50">{workflowsLoading ? <LoaderCircle size={14} className="animate-spin" /> : <RefreshCw size={14} />}Refresh versions</button></div>
      {activeVersion !== undefined && <p className="mt-4 text-xs text-slate-500">Currently active version: <span className="font-semibold text-slate-800">v{activeVersion}</span></p>}
      {versionsError && <div role="alert" className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">Could not load versions: {versionsError}</div>}
      {versionsLoading && <div className="mt-5 flex items-center gap-2 text-sm text-slate-500"><LoaderCircle size={16} className="animate-spin text-indigo-600" />Loading persisted versions…</div>}
      {!versionsLoading && versions && versions.length === 0 && <div className="mt-5"><EmptyState icon={GitBranch} title="No versions returned" description="The backend returned no persisted versions for this workflow." /></div>}
      {!versionsLoading && versions && versions.length > 0 && <div className="mt-5 overflow-hidden rounded-lg border border-slate-200"><div className="hidden grid-cols-[1fr_1.3fr_130px_160px] gap-4 bg-slate-50 px-4 py-3 text-[10px] font-semibold uppercase tracking-wide text-slate-400 sm:grid"><span>Version</span><span>Checksum</span><span>State</span><span>Action</span></div><div className="divide-y divide-slate-100">{versions.map((version) => <div key={`${version.workflow_id}-${version.version}`} className="grid gap-3 px-4 py-4 sm:grid-cols-[1fr_1.3fr_130px_160px] sm:items-center sm:gap-4"><div className="text-sm font-semibold text-slate-800">{version.workflow_id} <span className="text-slate-400">v{version.version}</span></div><div className="break-all font-mono text-[10px] text-slate-500">{version.checksum}</div><div><span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${version.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>{version.is_active ? 'Active' : 'Inactive'}</span></div><div>{version.is_active ? <span className="text-xs font-medium text-slate-400">Current version</span> : <button type="button" onClick={() => void activate(version)} disabled={!token || activatingVersion !== null} title={token ? 'Activate this version' : 'Enter the admin token to activate'} className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50">{activatingVersion === version.version ? <LoaderCircle size={14} className="animate-spin" /> : token ? <RefreshCw size={14} /> : <LockKeyhole size={14} />}{activatingVersion === version.version ? 'Activating…' : 'Activate version'}</button>}</div></div>)}</div></div>}
      {!token && versions && versions.some((version) => !version.is_active) && <p className="mt-4 inline-flex items-center gap-2 text-xs text-slate-500"><LockKeyhole size={14} />Admin access is required to activate an inactive version.</p>}
      {token && <p className="mt-4 inline-flex items-center gap-2 text-xs text-slate-500"><ShieldCheck size={14} />Activation is sent to the backend with your in-memory admin token.</p>}
    </section>
  </>
}
