// Placeholder page until the five screens land: shows the backend's /api/health.
import { Activity } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getHealth, type Health } from './api/health'

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch((e: Error) => setError(e.message))
  }, [])

  return (
    <div className="min-h-screen">
      <header className="bg-navy text-white">
        <div className="mx-auto flex max-w-5xl items-center gap-2.5 px-6 py-4">
          <span aria-hidden className="grid h-9 w-9 place-items-center rounded-lg bg-white text-navy">
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <path d="M8 19V5h9M8 12h6" />
            </svg>
          </span>
          <span className="flex flex-col leading-none">
            <span className="font-serif text-xl font-bold tracking-tight">FirstFix</span>
            <span className="mt-0.5 text-[0.7rem] text-white/70">Field service dispatch</span>
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        <section className="card p-6">
          <p className="eyebrow flex items-center gap-1.5">
            <Activity className="h-3.5 w-3.5" aria-hidden /> Backend status
          </p>
          {error && (
            <p role="alert" className="mt-3 text-sm text-bad">
              {error}
            </p>
          )}
          {!error && !health && <p className="mt-3 text-sm text-muted">Checking /api/health…</p>}
          {health && (
            <dl className="mt-3 grid grid-cols-[8rem_1fr] gap-y-1.5 text-sm">
              <dt className="text-muted">Status</dt>
              <dd className="font-medium text-ok">{health.status}</dd>
              <dt className="text-muted">App</dt>
              <dd>
                {health.app} {health.version} ({health.environment})
              </dd>
              <dt className="text-muted">Database</dt>
              <dd>{health.database}</dd>
              <dt className="text-muted">LLM</dt>
              <dd>{health.llm}</dd>
            </dl>
          )}
        </section>
      </main>
    </div>
  )
}
