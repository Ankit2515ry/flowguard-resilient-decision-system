import { useMemo } from 'react'
import { ArrowRight, History } from 'lucide-react'
import EmptyState from './EmptyState'
import type { AuditEvent } from '../types/evidence'

function timestamp(value: string) {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}

export default function AuditTimeline({ events }: { events: AuditEvent[] }) {
  const ordered = useMemo(() => [...events].sort((left, right) => left.sequence - right.sequence), [events])

  if (ordered.length === 0) {
    return <EmptyState icon={History} title="No audit events returned" description="The backend has not returned any persisted audit records for this request." />
  }

  return <ol className="relative space-y-0" aria-label="Persisted request audit timeline">
    {ordered.map((event, index) => <li key={`${event.sequence}-${event.event_type}`} className="relative flex gap-4 pb-6 last:pb-0">
      {index < ordered.length - 1 && <span aria-hidden="true" className="absolute left-[13px] top-7 h-[calc(100%-12px)] w-px bg-slate-200" />}
      <span className="relative z-[1] mt-0.5 flex h-[27px] w-[27px] shrink-0 items-center justify-center rounded-full border border-indigo-100 bg-indigo-50 text-[10px] font-bold text-indigo-700">{event.sequence}</span>
      <div className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-start"><div><h4 className="text-sm font-semibold text-slate-800">{event.event_type.replaceAll('_', ' ')}</h4><p className="mt-1 text-xs text-slate-500">{timestamp(event.created_at)}</p></div><span className="w-fit rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600">Version {event.config_version}</span></div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs"><span className="rounded-md bg-slate-50 px-2 py-1 font-medium text-slate-600">{event.old_state ?? '—'}</span><ArrowRight size={13} className="text-slate-400" /><span className="rounded-md bg-indigo-50 px-2 py-1 font-semibold text-indigo-700">{event.new_state}</span>{event.stage && <span className="ml-1 text-slate-500">Stage: <span className="font-medium text-slate-700">{event.stage}</span></span>}</div>
        {Object.keys(event.details ?? {}).length > 0 && <details className="mt-3 border-t border-slate-100 pt-2"><summary className="cursor-pointer text-xs font-medium text-slate-500 hover:text-slate-700">Persisted event details</summary><pre className="mt-2 max-h-48 overflow-auto rounded-md bg-slate-50 p-3 text-[11px] leading-5 text-slate-600">{JSON.stringify(event.details, null, 2)}</pre></details>}
      </div>
    </li>)}
  </ol>
}
