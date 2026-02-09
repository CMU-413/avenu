import { useState } from 'react'
import './App.css'

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5001'

type UserRecord = Record<string, unknown>

const detailLabelOverrides: Record<string, string> = {
  updated: 'Last updated',
  updatedAt: 'Last updated',
  updated_at: 'Last updated',
  lastUpdated: 'Last updated',
  last_updated: 'Last updated',
  createdAt: 'Created',
  created_at: 'Created',
}

const humanizeKey = (key: string) => {
  const humanized = key
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[-_]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  return humanized
    .split(' ')
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ')
}

function App() {
  const [users, setUsers] = useState<UserRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastFetchedAt, setLastFetchedAt] = useState<string | null>(null)

  const handleFetchUsers = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`${API_BASE_URL}/users`)
      if (!response.ok) {
        const errorBody = (await response.json().catch(() => ({}))) as
          | Record<string, unknown>
          | undefined
        const message =
          errorBody && 'error' in errorBody
            ? String(errorBody.error)
            : 'Failed to load users'
        throw new Error(message)
      }

      const payload = (await response.json()) as UserRecord[]
      setUsers(payload)
      setLastFetchedAt(new Date().toLocaleTimeString())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }

  const emptyStateText =
    users.length === 0 && !loading
      ? 'No users loaded yet. Click the button above to list users from the database.'
      : null

  const statusMessage = lastFetchedAt
    ? `Last refreshed ${lastFetchedAt}`
    : 'Not refreshed yet'

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Database</p>
          <h1>Users in the system</h1>
        </div>
        <p className="subtitle">
          Press the button below to fetch the latest users from the backend.
        </p>
      </header>

      <section className="controls">
        <button
          type="button"
          onClick={handleFetchUsers}
          disabled={loading}
          className={loading ? 'is-loading' : undefined}
          aria-busy={loading}
        >
          <span>{loading ? 'Loading users…' : 'List users from DB'}</span>
        </button>
        <p className="status">
          <span>Status:</span> {statusMessage}
        </p>
        {error && <p className="error">{error}</p>}
      </section>

      <section className="list" aria-live="polite">
        {emptyStateText ? (
          <p className="empty-state">{emptyStateText}</p>
        ) : (
          <ul className="user-list">
            {users.map((user, index) => {
              const id = (user._id ?? user.id ?? '') as string
              const label =
                typeof user.name === 'string'
                  ? user.name
                  : typeof user.email === 'string'
                    ? user.email
                    : id || `User ${index + 1}`

              const detailEntries = Object.entries(user).filter(
                ([key]) =>
                  key !== '_id' &&
                  key !== 'id' &&
                  key !== 'name' &&
                  key !== 'email',
              )

              return (
                <li key={id || `user-${index}`} className="user-card">
                  <p className="user-title">{label}</p>
                  {typeof user.email === 'string' && (
                    <p className="user-meta">
                      <span>Email:</span> {user.email}
                    </p>
                  )}
                  {id && (
                    <p className="user-id">
                      <span>ID:</span> {id}
                    </p>
                  )}
                  {detailEntries.length > 0 && (
                    <div className="detail-grid">
                      {detailEntries.map(([key, value]) => (
                        <div key={key} className="detail-row">
                          <span className="detail-label">
                            {detailLabelOverrides[key] ?? humanizeKey(key)}:
                          </span>
                          <span className="detail-value">
                            {String(value)}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </section>
    </div>
  )
}

export default App
