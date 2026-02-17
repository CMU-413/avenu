import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './App.css'
import AdminMailIntakeForm from './AdminMailIntakeForm'

// const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5001'

function App() {
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

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/mailIntake/:mailboxId" element={<AdminMailIntakeForm />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App