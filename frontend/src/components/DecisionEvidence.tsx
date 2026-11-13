import { CheckCircle2, CircleHelp, Clock3, ExternalLink, XCircle } from 'lucide-react'
import EmptyState from './EmptyState'
import type { DecisionExplanation, ExternalResult, RuleTrace } from '../types/evidence'

function valueText(value: unknown) {
  if (value === undefined) return 'Not provided'
  if (typeof value === 'string') return value
  const serialized = JSON.stringify(value)
  return serialized === undefined ? String(value) : serialized
}

function RuleTraceCard({ trace }: { trace: RuleTrace }) {
  const Icon = trace.passed ? CheckCircle2 : XCircle
  return <article className="rounded-lg border border-slate-200 bg-white p-4">
    <div className="flex flex-wrap items-start justify-between gap-2"><div><h4 className="text-sm font-semibold text-slate-800">{trace.rule_id}</h4><p className="mt-1 break-all font-mono text-[11px] text-slate-500">{trace.expression_reference}</p></div><span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold ${trace.passed ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'}`}><Icon size={13} />{trace.passed ? 'Passed' : 'Failed'}</span></div>
    <div className="mt-4 grid gap-3 sm:grid-cols-3"><div className="rounded-md bg-slate-50 p-3"><p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Actual</p><p className="mt-1 break-words font-mono text-xs text-slate-700">{valueText(trace.actual_value)}</p></div><div className="rounded-md bg-slate-50 p-3"><p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Operator</p><p className="mt-1 font-mono text-xs font-semibold text-slate-700">{trace.operator}</p></div><div className="rounded-md bg-slate-50 p-3"><p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Expected</p><p className="mt-1 break-words font-mono text-xs text-slate-700">{valueText(trace.expected_value)}</p></div></div>
    <p className="mt-3 text-xs leading-5 text-slate-600"><span className="font-semibold text-slate-700">Backend reason:</span> {trace.reason}</p>
    <p className="mt-2 text-[10px] text-slate-400">Failure action: {trace.failure_action} <span className="px-1">·</span> Config v{trace.config_version}</p>
  </article>
}

function ExternalAttempt({ attempt }: { attempt: ExternalResult }) {
  const Icon = attempt.success ? CheckCircle2 : attempt.retryable ? Clock3 : XCircle
  const color = attempt.success ? 'text-emerald-700 bg-emerald-50' : attempt.retryable ? 'text-amber-700 bg-amber-50' : 'text-rose-700 bg-rose-50'
  return <article className="flex gap-3 rounded-lg border border-slate-200 bg-white p-4">
    <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${color}`}><Icon size={17} /></div>
    <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center justify-between gap-2"><h4 className="text-sm font-semibold text-slate-800">{attempt.operation}</h4><span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${color}`}>{attempt.success ? 'Succeeded' : attempt.retryable ? 'Retryable failure' : 'Failed'}</span></div><p className="mt-1 text-xs text-slate-500">Attempt {attempt.attempt} <span className="px-1">·</span> Stage {attempt.stage_id} <span className="px-1">·</span> {attempt.category}</p><p className="mt-2 break-words text-xs leading-5 text-slate-600">{attempt.message}</p><p className="mt-2 break-all font-mono text-[10px] text-slate-400">Operation key: {attempt.operation_key}</p></div>
  </article>
}

export default function DecisionEvidence({ explanation }: { explanation: DecisionExplanation }) {
  return <div className="space-y-6">
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Backend explanation</p><h3 className="mt-1 text-base font-semibold text-slate-900">Decision status</h3></div><span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold ${explanation.pending ? 'bg-amber-50 text-amber-800' : 'bg-emerald-50 text-emerald-800'}`}>{explanation.pending ? <CircleHelp size={14} /> : <CheckCircle2 size={14} />}{explanation.pending ? 'Decision pending' : `Outcome: ${explanation.decision_outcome ?? explanation.status}`}</span></div>
      <p className="mt-3 text-sm leading-6 text-slate-600">{explanation.summary}</p>
      <p className="mt-3 text-xs text-slate-500">{explanation.pending ? 'Current status' : 'Terminal status'}: <span className="font-semibold text-slate-700">{explanation.status}</span> <span className="px-1">·</span> Configuration version {explanation.config_version}</p>
      {explanation.review_resolution && <div className="mt-4 rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-600"><p className="font-semibold text-slate-700">Review resolution returned by backend</p><pre className="mt-2 overflow-auto text-[11px]">{JSON.stringify(explanation.review_resolution, null, 2)}</pre></div>}
    </section>

    <section><div className="mb-3 flex items-center justify-between"><div><p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">Rule evaluation</p><h3 className="mt-1 text-base font-semibold text-slate-900">Persisted rule traces</h3></div><span className="text-xs text-slate-400">{explanation.rule_traces.length} returned</span></div>
      {explanation.rule_traces.length ? <div className="space-y-3">{explanation.rule_traces.map((trace, index) => <RuleTraceCard key={`${trace.rule_id}-${trace.config_version}-${index}`} trace={trace} />)}</div> : <EmptyState icon={CircleHelp} title="No rule traces available yet" description={explanation.pending ? 'The backend has not recorded rule evaluations for this request yet. Execute or refresh the request to see persisted results.' : 'The backend returned no rule traces for this request.'} />}
    </section>

    <section><div className="mb-3 flex items-center justify-between"><div><p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">External verification</p><h3 className="mt-1 text-base font-semibold text-slate-900">Attempt history</h3></div><span className="text-xs text-slate-400">{explanation.external_results.length} returned</span></div>
      {explanation.external_results.length ? <div className="space-y-3">{explanation.external_results.map((attempt, index) => <ExternalAttempt key={`${attempt.stage_id}-${attempt.attempt}-${index}`} attempt={attempt} />)}</div> : <EmptyState icon={ExternalLink} title="No external attempts recorded" description={explanation.pending ? 'No external verification attempt has been persisted yet for this request.' : 'The backend returned no external verification attempts.'} />}
    </section>
  </div>
}
