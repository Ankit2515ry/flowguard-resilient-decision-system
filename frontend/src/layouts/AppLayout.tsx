import { useState } from 'react'
import { ArrowUpRight, CircleHelp, Command, FilePlus2, GitBranch, LayoutDashboard, Menu, Search, ShieldCheck, X } from 'lucide-react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useBackendHealth } from '../hooks/useBackendHealth'

const navigation = [
  { label: 'Dashboard', to: '/', icon: LayoutDashboard, end: true },
  { label: 'Submit request', to: '/submit', icon: FilePlus2 },
  { label: 'Request details', to: '/requests', icon: Search },
  { label: 'Manual reviews', to: '/reviews', icon: ShieldCheck },
  { label: 'Workflow configuration', to: '/workflows', icon: GitBranch },
]

const pageTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/submit': 'Submit request',
  '/requests': 'Request details',
  '/reviews': 'Manual reviews',
  '/workflows': 'Workflow configuration',
}

function Sidebar({ onNavigate, mobile = false }: { onNavigate?: () => void; mobile?: boolean }) {
  return (
    <>
      <div className="flex h-[76px] items-center gap-3 px-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-sm shadow-indigo-200">
          <Command size={21} strokeWidth={2.4} />
        </div>
        <div>
          <div className="text-[17px] font-bold tracking-tight text-slate-900">FlowGuard</div>
          <div className="text-[11px] font-medium tracking-wide text-slate-400">DECISION PLATFORM</div>
        </div>
        {mobile && <button onClick={onNavigate} className="ml-auto rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Close menu"><X size={19} /></button>}
      </div>
      <div className="px-4 pt-6">
        <p className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-400">Workspace</p>
        <nav className="space-y-1" aria-label="Main navigation">
          {navigation.map(({ label, to, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} onClick={onNavigate} className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}>
              <Icon size={18} strokeWidth={1.9} /><span>{label}</span>
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="mt-auto p-4">
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-slate-700"><CircleHelp size={15} className="text-indigo-500" /> Need a hand?</div>
          <p className="text-xs leading-5 text-slate-500">Use the API docs to explore supported workflow behavior.</p>
          <a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-700">Open API docs <ArrowUpRight size={13} /></a>
        </div>
        <div className="mt-4 border-t border-slate-100 px-2 pt-4 text-[11px] text-slate-400">FlowGuard · Operator console</div>
      </div>
    </>
  )
}

export default function AppLayout() {
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()
  const { state, refresh } = useBackendHealth()
  const title = pageTitles[location.pathname] ?? 'Page not found'
  const statusLabel = state === 'connected' ? 'Backend connected' : state === 'checking' ? 'Checking backend' : 'Backend unavailable'

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-[258px] flex-col border-r border-slate-200 bg-white lg:flex"><Sidebar /></aside>
      {menuOpen && <div className="fixed inset-0 z-40 lg:hidden"><button className="absolute inset-0 bg-slate-950/30" aria-label="Close navigation" onClick={() => setMenuOpen(false)} /><aside className="absolute inset-y-0 left-0 flex w-[280px] flex-col bg-white shadow-xl"><Sidebar mobile onNavigate={() => setMenuOpen(false)} /></aside></div>}
      <div className="lg:pl-[258px]">
        <header className="sticky top-0 z-10 flex h-[76px] items-center justify-between border-b border-slate-200 bg-white/95 px-5 backdrop-blur sm:px-8">
          <div className="flex items-center gap-3">
            <button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 lg:hidden" onClick={() => setMenuOpen(true)} aria-label="Open navigation"><Menu size={20} /></button>
            <div><p className="text-[11px] font-medium text-slate-400">Workspace <span className="px-1">/</span> <span className="text-slate-600">{title}</span></p><h1 className="mt-0.5 text-[18px] font-semibold tracking-tight text-slate-900">{title}</h1></div>
          </div>
          <button onClick={refresh} title="Check backend connection" className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 shadow-sm hover:bg-slate-50">
            <span className={`h-2 w-2 rounded-full ${state === 'connected' ? 'bg-emerald-500' : state === 'checking' ? 'animate-pulse bg-amber-400' : 'bg-rose-500'}`} />
            <span className="hidden sm:inline">{statusLabel}</span><span className="sm:hidden">{state === 'connected' ? 'Online' : state === 'checking' ? 'Checking' : 'Offline'}</span>
          </button>
        </header>
        <main className="mx-auto max-w-[1440px] px-5 py-7 sm:px-8 sm:py-9"><Outlet /></main>
      </div>
    </div>
  )
}
