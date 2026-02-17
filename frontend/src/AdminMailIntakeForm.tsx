import { useEffect, useMemo, useState } from 'react'

const API_BASE_URL = '/api'

type MailboxRecord = {
  id: string
  displayName: string
}

type MailRecord = {
  id: string
  mailboxId: string
  type: 'letter' | 'package'
  count: number
  date: string
}

type EditState = {
  type: 'letter' | 'package'
  count: number
  date: string
}

type AdminMailIntakeFormProps = {
  isAuthenticated: boolean
  onUnauthorized: () => void
}

function dateInputToday(): string {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 10)
}

function datetimeLocalFromIso(isoValue: string): string {
  const rawDate = new Date(isoValue)
  const local = new Date(rawDate.getTime() - rawDate.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 16)
}

function isoFromDatetimeLocal(localValue: string): string {
  return new Date(localValue).toISOString()
}

function AdminMailIntakeForm({ isAuthenticated, onUnauthorized }: AdminMailIntakeFormProps) {
  const [dateFilter, setDateFilter] = useState(dateInputToday)
  const [mailboxFilter, setMailboxFilter] = useState('')
  const [mailboxes, setMailboxes] = useState<MailboxRecord[]>([])
  const [records, setRecords] = useState<MailRecord[]>([])
  const [editState, setEditState] = useState<Record<string, EditState>>({})
  const [savingId, setSavingId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  useEffect(() => {
    if (!isAuthenticated) {
      return
    }

    let cancelled = false
    const run = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/mailboxes`, { credentials: 'include' })
        if (response.status === 401) {
          onUnauthorized()
          return
        }
        if (response.status === 403) {
          setError('Forbidden: admin privileges required')
          return
        }
        if (!response.ok) {
          setError('Failed to load mailboxes')
          return
        }
        const payload = (await response.json()) as MailboxRecord[]
        if (!cancelled) {
          setMailboxes(payload)
        }
      } catch {
        if (!cancelled) {
          setError('Failed to load mailboxes')
        }
      }
    }
    run()
    return () => {
      cancelled = true
    }
  }, [isAuthenticated, onUnauthorized])

  const loadRecords = async () => {
    if (!isAuthenticated) {
      return
    }
    setLoading(true)
    setError(null)
    setSuccess(null)
    try {
      const query = new URLSearchParams({ date: dateFilter })
      if (mailboxFilter) {
        query.set('mailboxId', mailboxFilter)
      }
      const response = await fetch(`${API_BASE_URL}/mail?${query.toString()}`, {
        credentials: 'include',
      })
      if (response.status === 401) {
        onUnauthorized()
        return
      }
      if (response.status === 403) {
        setError('Forbidden: admin privileges required')
        return
      }
      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as { error?: string }
        setError(body.error ?? 'Failed to load mail records')
        return
      }
      const payload = (await response.json()) as MailRecord[]
      setRecords(payload)
      setEditState(
        Object.fromEntries(
          payload.map((record) => [
            record.id,
            {
              type: record.type,
              count: record.count,
              date: datetimeLocalFromIso(record.date),
            },
          ]),
        ),
      )
    } catch {
      setError('Failed to load mail records')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadRecords()
    // reload when filters/auth change
  }, [dateFilter, mailboxFilter, isAuthenticated])

  const mailboxNameById = useMemo(
    () => Object.fromEntries(mailboxes.map((mailbox) => [mailbox.id, mailbox.displayName])),
    [mailboxes],
  )

  const groupedRecords = useMemo(() => {
    const groups: Record<string, MailRecord[]> = {}
    for (const record of records) {
      const key = record.mailboxId
      if (!groups[key]) {
        groups[key] = []
      }
      groups[key].push(record)
    }
    return Object.entries(groups).sort((a, b) => {
      const leftName = mailboxNameById[a[0]] ?? a[0]
      const rightName = mailboxNameById[b[0]] ?? b[0]
      return leftName.localeCompare(rightName)
    })
  }, [mailboxNameById, records])

  const updateRecordField = (id: string, key: keyof EditState, value: EditState[keyof EditState]) => {
    setEditState((current) => ({
      ...current,
      [id]: { ...current[id], [key]: value } as EditState,
    }))
  }

  const saveRecord = async (record: MailRecord) => {
    const edited = editState[record.id]
    if (!edited || !edited.date) {
      setError('Date is required')
      return
    }
    if (!Number.isInteger(edited.count) || edited.count < 1) {
      setError('Count must be a whole number >= 1')
      return
    }

    setSavingId(record.id)
    setError(null)
    setSuccess(null)
    try {
      const response = await fetch(`${API_BASE_URL}/mail/${record.id}`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: edited.type,
          count: edited.count,
          date: isoFromDatetimeLocal(edited.date),
        }),
      })
      if (response.status === 401) {
        onUnauthorized()
        return
      }
      if (response.status === 403) {
        setError('Forbidden: admin privileges required')
        return
      }
      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as { error?: string }
        setError(body.error ?? 'Failed to save record')
        return
      }

      setSuccess('Record updated')
      await loadRecords()
    } catch {
      setError('Failed to save record')
    } finally {
      setSavingId(null)
    }
  }

  const summary = useMemo(() => {
    const totals = { letter: 0, package: 0 }
    for (const record of records) {
      totals[record.type] += record.count
    }
    return totals
  }, [records])

  return (
    <div style={{ padding: '1rem', maxWidth: '1000px', margin: '0 auto' }}>
      <h2>Mail Intake Review</h2>
      {!isAuthenticated && <p>Log in from the home page to review and edit mail records.</p>}
      {isAuthenticated && (
        <>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
            <label>
              Date
              <input
                type="date"
                value={dateFilter}
                onChange={(event) => setDateFilter(event.target.value)}
                style={{ marginLeft: '0.5rem' }}
              />
            </label>
            <label>
              Mailbox
              <select
                value={mailboxFilter}
                onChange={(event) => setMailboxFilter(event.target.value)}
                style={{ marginLeft: '0.5rem' }}
              >
                <option value="">All mailboxes</option>
                {mailboxes.map((mailbox) => (
                  <option key={mailbox.id} value={mailbox.id}>
                    {mailbox.displayName}
                  </option>
                ))}
              </select>
            </label>
            <button onClick={() => void loadRecords()} disabled={loading}>
              {loading ? 'Loading...' : 'Refresh'}
            </button>
          </div>

          <p>
            Inspect counts for {dateFilter}: letters={summary.letter}, packages={summary.package}
          </p>
          {error && <p style={{ color: 'red' }}>{error}</p>}
          {success && <p style={{ color: 'green' }}>{success}</p>}

          {groupedRecords.length === 0 && !loading && <p>No records found for this date.</p>}

          {groupedRecords.map(([mailboxId, mailboxRecords]) => {
            const mailboxLetterCount = mailboxRecords
              .filter((item) => item.type === 'letter')
              .reduce((total, item) => total + item.count, 0)
            const mailboxPackageCount = mailboxRecords
              .filter((item) => item.type === 'package')
              .reduce((total, item) => total + item.count, 0)
            return (
              <section key={mailboxId} style={{ marginTop: '1.25rem' }}>
                <h3>{mailboxNameById[mailboxId] ?? mailboxId}</h3>
                <p>
                  Mailbox totals: letters={mailboxLetterCount}, packages={mailboxPackageCount}
                </p>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      <th align="left">Type</th>
                      <th align="left">Count</th>
                      <th align="left">Date/Time</th>
                      <th align="left">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mailboxRecords.map((record) => {
                      const edited = editState[record.id]
                      if (!edited) {
                        return null
                      }
                      return (
                        <tr key={record.id}>
                          <td>
                            <select
                              value={edited.type}
                              onChange={(event) =>
                                updateRecordField(
                                  record.id,
                                  'type',
                                  event.target.value as 'letter' | 'package',
                                )
                              }
                            >
                              <option value="letter">letter</option>
                              <option value="package">package</option>
                            </select>
                          </td>
                          <td>
                            <input
                              type="number"
                              min={1}
                              value={edited.count}
                              onChange={(event) =>
                                updateRecordField(record.id, 'count', Number(event.target.value))
                              }
                              style={{ width: '6rem' }}
                            />
                          </td>
                          <td>
                            <input
                              type="datetime-local"
                              value={edited.date}
                              onChange={(event) => updateRecordField(record.id, 'date', event.target.value)}
                            />
                          </td>
                          <td>
                            <button onClick={() => void saveRecord(record)} disabled={savingId === record.id}>
                              {savingId === record.id ? 'Saving...' : 'Save'}
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </section>
            )
          })}
        </>
      )}
    </div>
  )
}

export default AdminMailIntakeForm
