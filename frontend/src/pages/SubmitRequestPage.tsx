import { FilePlus2, LockKeyhole } from 'lucide-react'
import EmptyState from '../components/EmptyState'
import PageHeading from '../components/PageHeading'

export default function SubmitRequestPage() {
  return <><PageHeading eyebrow="Intake" title="Submit a request" description="Request intake will be available in a later phase. Submitting and executing requests are separate backend operations." /><div className="mb-5 flex items-start gap-3 rounded-xl border border-blue-100 bg-blue-50/70 p-4 text-sm leading-6 text-blue-900"><LockKeyhole size={18} className="mt-0.5 shrink-0 text-blue-600" /><p>This Phase 1 workspace is read-only. No request data is sent to the backend.</p></div><EmptyState icon={FilePlus2} title="Request intake is not enabled yet" description="The backend requires a workflow-specific payload and an Idempotency-Key. The submission form will be added after those inputs are connected to the API." /></>
}
