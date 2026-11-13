import type { LucideIcon } from 'lucide-react'
export default function EmptyState({ icon: Icon, title, description }: { icon: LucideIcon; title: string; description: string }) {
  return <div className="flex min-h-[228px] flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center"><div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600"><Icon size={22} strokeWidth={1.8} /></div><h3 className="text-sm font-semibold text-slate-800">{title}</h3><p className="mt-2 max-w-md text-sm leading-6 text-slate-500">{description}</p></div>
}
