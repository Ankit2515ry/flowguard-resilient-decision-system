import { useEffect, useState } from 'react'
import { Activity, ArrowRight, ClipboardList, FilePlus2, GitBranch, LoaderCircle, ShieldCheck, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getWorkflows } from '../api/workflows'
import EmptyState from '../components/EmptyState'
import PageHeading from '../components/PageHeading'
import type { WorkflowSummary } from '../types/workflow'

const shortcuts = [
  { label: 'Submit a request', detail: 'Start a new workflow intake', to: '/submit', icon: FilePlus2 },
  { label: 'Look up a request', detail: 'Open a request by its ID', to: '/requests', icon: ClipboardList },
  { label: 'Review a case', detail: 'Access the manual review queue', to: '/reviews', icon: ShieldCheck },
  { label: 'Workflow versions', detail: 'Inspect configured workflows', to: '/workflows', icon: GitBranch },
]

export default function DashboardPage() {
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    getWorkflows(controller.signal)
      .then(setWorkflows)
      .catch((cause: unknown) => {
        if (!(cause instanceof DOMException && cause.name === 'AbortError')) setError(cause instanceof Error ? cause.message : 'Could not load workflows.')
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  return <>
    <PageHeading eyebrow="Overview" title="Welcome to FlowGuard" description="A clear workspace for running and reviewing configured decisions. All workflow outcomes and state changes are provided by the backend." />
    <section className="mb-7 rounded-2xl border border-indigo-100 bg-gradient-to-r from-indigo-50/80 to-white p-6 sm:p-8">
      <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-center"><div className="max-w-xl"><div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-indigo-600"><Sparkles size={15} /> Operator workspace</div><h3 className="text-xl font-semibold tracking-tight text-slate-900">Your workflow console is ready</h3><p className="mt-2 text-sm leading-6 text-slate-600">Choose an action to get started. Live workflow versions below come directly from the FlowGuard API.</p></div><Link to="/submit" className="inline-flex shrink-0 items-center justify-center gap-2 self-start rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 sm:self-center">Submit request <ArrowRight size={16} /></Link></div>
    </section>
    <div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-semibold text-slate-800">Quick access</h3><span className="text-xs text-slate-400">Choose a workspace area</span></div>
    <div className="mb-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{shortcuts.map(({ label, detail, to, icon: Icon }) => <Link key={to} to={to} className="group rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-indigo-200 hover:shadow-md"><div className="mb-5 flex h-10 w-10 items-center justify-center rounded-lg bg-slate-50 text-slate-600 group-hover:bg-indigo-50 group-hover:text-indigo-600"><Icon size={19} /></div><div className="flex items-center justify-between"><div><p className="text-sm font-semibold text-slate-800">{label}</p><p className="mt-1 text-xs text-slate-500">{detail}</p></div><ArrowRight size={16} className="text-slate-300 group-hover:text-indigo-500" /></div></Link>)}</div>
    <div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-semibold text-slate-800">Available workflows</h3><span className="text-xs text-slate-400">GET /api/v1/workflows</span></div>
    {loading ? <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-600"><LoaderCircle size={16} className="animate-spin text-indigo-600" /> Loading workflows…</div>
      : error ? <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">Could not load available workflows: {error}</div>
        : workflows.length === 0 ? <EmptyState icon={GitBranch} title="No active workflows" description="The backend did not return any active workflows. Check the API's configured workflow snapshots." />
          : <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{workflows.map((workflow) => <div key={workflow.workflow_id} className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600"><Activity size={18} /></div><div className="min-w-0"><p className="truncate text-sm font-semibold text-slate-800">{workflow.workflow_id}</p><p className="mt-1 text-xs text-slate-500">Active version <span className="font-semibold text-slate-700">v{workflow.active_version}</span></p></div></div>)}</div>}
    <div className="mb-3 mt-8 flex items-center justify-between"><h3 className="text-sm font-semibold text-slate-800">Request lookup</h3><span className="text-xs text-slate-400">No request-list endpoint</span></div>
    <EmptyState icon={ClipboardList} title="Look up a request by UUID" description="The backend does not provide request history or aggregate counts. Use Request Details to retrieve a specific persisted request." />
  </>
}
