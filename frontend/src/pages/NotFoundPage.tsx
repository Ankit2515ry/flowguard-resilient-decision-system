import { Link } from 'react-router-dom'
export default function NotFoundPage() {
  return <div className="flex min-h-[55vh] flex-col items-center justify-center text-center"><p className="text-sm font-bold uppercase tracking-widest text-indigo-600">404</p><h2 className="mt-3 text-2xl font-semibold text-slate-900">Page not found</h2><p className="mt-2 text-sm text-slate-500">The page you are looking for does not exist.</p><Link to="/" className="mt-5 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700">Return to dashboard</Link></div>
}
