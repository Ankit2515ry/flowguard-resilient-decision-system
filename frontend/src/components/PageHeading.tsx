export default function PageHeading({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return <div className="mb-7"><p className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-indigo-600">{eyebrow}</p><h2 className="text-2xl font-semibold tracking-tight text-slate-900 sm:text-[28px]">{title}</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">{description}</p></div>
}
