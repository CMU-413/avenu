import { useState } from 'react'
import type { FormEvent } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import './App.css'
import AdminMailIntakeForm from './AdminMailIntakeForm'

const API_BASE_URL = '/api'

type UserRecord = Record<string, unknown>

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    ...init,
  })
}

function App() {
  const [users, setUsers] = useState<UserRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastFetchedAt, setLastFetchedAt] = useState<string | null>(null)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [loggingIn, setLoggingIn] = useState(false)
  const [loginError, setLoginError] = useState<string | null>(null)
  const [email, setEmail] = useState('')

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setLoggingIn(true)
    setLoginError(null)

    try {
      const response = await apiFetch('/session/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })

      if (response.status === 204) {
        setIsAuthenticated(true)
        return
      }

      setIsAuthenticated(false)
      setLoginError(response.status === 401 ? 'Unknown user email' : 'Login failed')
    } catch {
      setLoginError('Login failed')
    } finally {
      setLoggingIn(false)
    }
  }

  const handleLogout = async () => {
    try {
      await apiFetch('/session/logout', { method: 'POST' })
    } finally {
      setIsAuthenticated(false)
      setUsers([])
      setLastFetchedAt(null)
    }
  }

  const handleFetchUsers = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await apiFetch('/users')
      if (response.status === 401) {
        setIsAuthenticated(false)
        throw new Error('Unauthorized: please log in again')
      }
      if (response.status === 403) {
        throw new Error('Forbidden: admin privileges required')
      }
      if (!response.ok) {
        const errorBody = (await response.json().catch(() => ({}))) as
          | Record<string, unknown>
          | undefined
        const message =
          errorBody && 'error' in errorBody ? String(errorBody.error) : 'Failed to load users'
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

  const statusMessage = lastFetchedAt ? `Last refreshed ${lastFetchedAt}` : 'Not refreshed yet'

  const HomePage = () => (
    <div style={{ padding: '1rem' }}>
      <h1>Avenu Admin</h1>

      {!isAuthenticated && (
        <form onSubmit={handleLogin} style={{ marginBottom: '1rem' }}>
          <div>
            <label>
              User Email
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </label>
          </div>
          <button type="submit" disabled={loggingIn}>
            {loggingIn ? 'Logging in...' : 'Login'}
          </button>
          {loginError && <p style={{ color: 'red' }}>{loginError}</p>}
        </form>
      )}

      {isAuthenticated && (
        <p>
          Session active. <button onClick={handleLogout}>Logout</button>
        </p>
      )}

      <button onClick={handleFetchUsers} disabled={loading || !isAuthenticated}>
        {loading ? 'Loading...' : 'Fetch Users'}
      </button>

      {error && <p style={{ color: 'red' }}>{error}</p>}
      {statusMessage && <p>{statusMessage}</p>}
      {emptyStateText && <p>{emptyStateText}</p>}
      {users.length > 0 && (
        <pre style={{ marginTop: '1rem', overflow: 'auto' }}>{JSON.stringify(users, null, 2)}</pre>
      )}
    </div>
  )

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/mailIntake/:mailboxId" element={<AdminMailIntakeForm />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
