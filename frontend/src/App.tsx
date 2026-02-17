import { useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './App.css'
import AdminMailIntakeForm from './AdminMailIntakeForm'

const API_BASE_URL =
  import.meta.env.VITE_API_URL ?? import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:5001'
const ADMIN_API_KEY = import.meta.env.VITE_ADMIN_API_KEY ?? ''

type UserRecord = Record<string, unknown>

const adminHeaders = (): HeadersInit => {
  const headers: HeadersInit = {}
  if (ADMIN_API_KEY) {
    headers['Authorization'] = `Bearer ${ADMIN_API_KEY}`
  }
  return headers
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
      const response = await fetch(`${API_BASE_URL}/users`, {
        headers: adminHeaders(),
      })
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

  const HomePage = () => (
    <div style={{ padding: '1rem' }}>
      <h1>Avenu Admin</h1>
      <button onClick={handleFetchUsers} disabled={loading}>
        {loading ? 'Loading...' : 'Fetch Users'}
      </button>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {statusMessage && <p>{statusMessage}</p>}
      {emptyStateText && <p>{emptyStateText}</p>}
      {users.length > 0 && (
        <pre style={{ marginTop: '1rem', overflow: 'auto' }}>
          {JSON.stringify(users, null, 2)}
        </pre>
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