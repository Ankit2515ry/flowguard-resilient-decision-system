import { GitBranch } from 'lucide-react'
import EmptyState from '../components/EmptyState'
import PageHeading from '../components/PageHeading'

export default function WorkflowConfigurationPage() {
  return <><PageHeading eyebrow="Configuration" title="Workflow configuration" description="Inspect active workflow versions and their persisted version history." /><div className="mb-5 rounded-xl border border-slate-200 bg-white p-4 text-sm leading-6 text-slate-600">Workflow definitions are immutable and versioned by the backend. This workspace will display API-provided versions; it will not edit rule files.</div><EmptyState icon={GitBranch} title="Workflow discovery is not connected" description="Workflow and version details will appear here after the discovery API is integrated. No example versions or configuration status are fabricated." /></>
}
