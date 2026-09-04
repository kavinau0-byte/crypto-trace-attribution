import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { FolderSearch, Radar } from 'lucide-react'
import { API_BASE_URL, getHealth } from '../api/client'

const NAV = [
  { to: '/', label: 'New trace', icon: Radar, end: true },
  { to: '/cases', label: 'Cases', icon: FolderSearch, end: false },
]

export default function AppShell() {
  const location = useLocation()

  return (
    <div className="flex min-h-full flex-col bg-void lg:h-full lg:flex-row">
      <nav className="flex shrink-0 flex-row items-center gap-4 border-b border-line bg-surface px-4 py-3 lg:w-60 lg:flex-col lg:items-stretch lg:gap-0 lg:border-r lg:border-b-0 lg:px-0 lg:py-0">
        <div className="lg:border-b lg:border-line lg:px-5 lg:py-5">
          <div className="text-[15px] font-semibold tracking-tight text-ink">
            Wallet Attribution
          </div>
          <div className="hidden text-[12px] text-ink-faint lg:block">
            Bitcoin tracing console
          </div>
        </div>

        <ul className="flex flex-1 flex-row gap-1 lg:flex-col lg:gap-0.5 lg:p-3">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={end}
                className={({ isActive }) =>
                  [
                    'relative flex items-center gap-2.5 rounded-sm px-3 py-2 text-[13px] font-medium transition-colors',
                    isActive
                      ? 'bg-raised text-accent'
                      : 'text-ink-dim hover:bg-raised/60 hover:text-ink',
                  ].join(' ')
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive ? (
                      <span
                        className="absolute inset-y-1.5 -left-3 hidden w-0.5 rounded-full bg-accent lg:block"
                        aria-hidden="true"
                      />
                    ) : null}
                    <Icon size={15} strokeWidth={2} />
                    {label}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>

        <BackendStatus />
      </nav>

      <main className="min-w-0 flex-1 lg:overflow-y-auto">
        <div key={location.pathname} className="view-enter">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

/**
 * Live reachability of the API. During a demo the most common failure is a
 * backend that isn't running, so the console says so before a trace is
 * submitted rather than after it fails.
 */
function BackendStatus() {
  const [status, setStatus] = useState('checking')

  useEffect(() => {
    let cancelled = false
    async function check() {
      try {
        const data = await getHealth()
        if (!cancelled) setStatus(data?.status === 'ok' ? 'online' : 'degraded')
      } catch {
        if (!cancelled) setStatus('offline')
      }
    }
    check()
    const id = setInterval(check, 20000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  const tone = {
    checking: { dot: 'bg-ink-faint', text: 'Checking backend' },
    online: { dot: 'bg-match', text: 'Backend online' },
    degraded: { dot: 'bg-alert', text: 'Backend degraded' },
    offline: { dot: 'bg-alert', text: 'Backend unreachable' },
  }[status]

  return (
    <div className="ml-auto lg:mt-auto lg:ml-0 lg:border-t lg:border-line lg:px-5 lg:py-4">
      <div className="flex items-center gap-2">
        <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${tone.dot}`} aria-hidden="true" />
        <span className="text-[12px] text-ink-dim">{tone.text}</span>
      </div>
      <div
        className="data mt-1 hidden truncate text-[11px] text-ink-faint lg:block"
        title={API_BASE_URL}
      >
        {API_BASE_URL}
      </div>
    </div>
  )
}
