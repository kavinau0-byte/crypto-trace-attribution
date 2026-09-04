import { Link, Route, Routes } from 'react-router-dom'
import AppShell from './components/AppShell'
import SubmitTrace from './pages/SubmitTrace'
import CaseHistory from './pages/CaseHistory'
import CaseDetail from './pages/CaseDetail'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<SubmitTrace />} />
        <Route path="cases" element={<CaseHistory />} />
        <Route path="cases/:id" element={<CaseDetail />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}

function NotFound() {
  return (
    <div className="mx-auto max-w-2xl px-6 py-20">
      <h1 className="text-lg font-semibold text-ink">No such page</h1>
      <p className="mt-2 text-[14px] text-ink-dim">
        That route isn&apos;t part of the console.
      </p>
      <Link
        to="/"
        className="mt-6 inline-flex rounded-sm border border-line-strong px-3.5 py-2 text-[13px] font-medium text-ink transition-colors hover:border-accent hover:text-accent"
      >
        Start a trace
      </Link>
    </div>
  )
}
