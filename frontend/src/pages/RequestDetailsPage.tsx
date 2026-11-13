import { ClipboardList, Search } from 'lucide-react'
import EmptyState from '../components/EmptyState'
import PageHeading from '../components/PageHeading'

export default function RequestDetailsPage() {
  return <><PageHeading eyebrow="Requests" title="Request details" description="Inspect a request by its ID. The API exposes individual status, explanation, and audit endpoints, but does not provide a searchable request directory." /><div className="mb-5 flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-4 text-sm leading-6 text-slate-600"><Search size={18} className="mt-0.5 shrink-0 text-indigo-500" /><p>Request lookup will be connected in a later phase. You will need the request UUID returned by intake or provided by an operator.</p></div><EmptyState icon={ClipboardList} title="No request selected" description="Enter a request ID once request detail API integration is enabled. This page does not show sample or fabricated request data." /></>
}
