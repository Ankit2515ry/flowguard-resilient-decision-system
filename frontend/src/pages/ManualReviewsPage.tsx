import { ShieldCheck } from 'lucide-react'
import EmptyState from '../components/EmptyState'
import PageHeading from '../components/PageHeading'

export default function ManualReviewsPage() {
  return <><PageHeading eyebrow="Operations" title="Manual reviews" description="Review cases that the configured backend workflow has routed for human attention." /><div className="mb-5 flex items-start gap-3 rounded-xl border border-amber-100 bg-amber-50/70 p-4 text-sm leading-6 text-amber-900"><ShieldCheck size={18} className="mt-0.5 shrink-0 text-amber-600" /><p>The review queue requires the server-configured admin token. Secure in-memory admin access will be added in a later phase.</p></div><EmptyState icon={ShieldCheck} title="Review queue is not connected" description="No review data is shown until the authenticated review endpoint is integrated. This keeps the page honest when admin access has not been configured." /></>
}
