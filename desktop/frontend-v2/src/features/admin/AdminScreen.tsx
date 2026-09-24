import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, ApiError, type ChatMessage } from '../../lib/api'
import { useSession } from '../../lib/auth'
import { StrategyPanel } from './StrategyPanel'
import './admin.css'

interface Stats {
  total_users: number
  plus_users: number
  active_7d: number
  total_messages: number
  open_reports: number
  maintenance: { on: boolean; message: string }
}

interface AdminUser {
  id: number
  username: string
  email: string
  created_at: string | null
  last_login: string | null
  plus: boolean
  messages: number
}

interface ReportSummary {
  id: string
  at: string
  user_email: string
  note: string
  chat_title: string
  app_version: string
  msg_count: number
}

interface FullReport extends ReportSummary {
  messages: ChatMessage[]
  user_agent: string
  url: string
}

type Tab = 'users' | 'reports' | 'strategy' | 'maintenance'

function ago(iso: string | null): string {
  if (!iso) return '—'
  // SQLite/utcnow() timestamps are UTC but carry no offset; without the 'Z'
  // the browser would read them as local time.
  const normalized = iso.replace(' ', 'T')
  const hasZone = /(Z|[+-]\d\d:?\d\d)$/.test(normalized)
  const t = new Date(hasZone ? normalized : normalized + 'Z').getTime()
  if (Number.isNaN(t)) return '—'
  const s = (Date.now() - t) / 1000
  if (s < 90) return 'just now'
  if (s < 3600) return `${Math.round(s / 60)}m ago`
  if (s < 86400) return `${Math.round(s / 3600)}h ago`
  if (s < 86400 * 45) return `${Math.round(s / 86400)}d ago`
  return new Date(t).toLocaleDateString()
}

export function AdminScreen() {
  const [tab, setTab] = useState<Tab>('users')
  const stats = useQuery({
    queryKey: ['admin', 'stats'],
    queryFn: () => api.get<Stats>('/api/admin/stats'),
  })

  if (stats.error instanceof ApiError && stats.error.status === 403) {
    return (
      <div className="page">
        <div className="page-inner">
          <p className="card empty">This area is owner-only.</p>
        </div>
      </div>
    )
  }

  const s = stats.data
  return (
    <div className="page">
      <div className="page-inner">
        <header className="page-head">
          <div>
            <h1 className="page-title">Admin</h1>
            <p className="page-sub">Users, reports, strategy health and maintenance</p>
          </div>
          <div className="seg" role="tablist" aria-label="Section">
            {(['users', 'reports', 'strategy', 'maintenance'] as Tab[]).map((t) => (
              <button
                key={t}
                role="tab"
                aria-selected={tab === t}
                className={'seg-btn' + (tab === t ? ' seg-on' : '')}
                onClick={() => setTab(t)}
              >
                {t[0].toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
        </header>

        <div className="grid-stats">
          <Stat label="Users" value={s?.total_users} />
          <Stat label="Plus" value={s?.plus_users} />
          <Stat label="Active 7 days" value={s?.active_7d} />
          <Stat label="Messages" value={s?.total_messages} />
          <Stat label="Open reports" value={s?.open_reports} warn={!!s?.open_reports} />
        </div>

        {s?.maintenance.on && (
          <p className="note-warn">Maintenance mode is on — everyone but you sees the maintenance screen.</p>
        )}

        {tab === 'users' && <UsersPanel />}
        {tab === 'reports' && <ReportsPanel />}
        {tab === 'strategy' && <StrategyPanel />}
        {tab === 'maintenance' && s && (
          // Keyed so the draft message resets whenever the saved state changes.
          <MaintenancePanel key={`${s.maintenance.on}:${s.maintenance.message}`} current={s.maintenance} />
        )}
      </div>
    </div>
  )
}

function Stat({ label, value, warn }: { label: string; value: number | undefined; warn?: boolean }) {
  return (
    <div className="card stat">
      <span className="stat-label">{label}</span>
      <span className={'stat-value' + (warn ? ' admin-stat-warn' : '')}>{value ?? '—'}</span>
    </div>
  )
}

// ── Users ────────────────────────────────────────────────────────────────

function UsersPanel() {
  const qc = useQueryClient()
  const { user: me } = useSession()
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null)
  const [filter, setFilter] = useState('')
  const users = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: () => api.get<{ users: AdminUser[] }>('/api/admin/users'),
  })

  const invalidate = () => qc.invalidateQueries({ queryKey: ['admin'] })
  const setPlus = useMutation({
    mutationFn: (v: { user_id: number; on: boolean }) => api.post('/api/admin/set-plus', v),
    onSuccess: invalidate,
  })
  const remove = useMutation({
    mutationFn: (id: number) => api.del(`/api/admin/users/${id}`),
    onSuccess: () => {
      setConfirmDelete(null)
      invalidate()
    },
  })

  if (users.isPending) return <p className="admin-empty">Loading users…</p>
  if (users.error) return <p className="admin-error">{users.error.message}</p>

  const q = filter.trim().toLowerCase()
  const rows = users.data.users.filter(
    (u) => !q || u.email.toLowerCase().includes(q) || u.username.toLowerCase().includes(q),
  )
  const mutationError = setPlus.error ?? remove.error

  return (
    <section className="card admin-panel">
      <input
        className="input admin-filter"
        placeholder="Filter by name or email"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      {mutationError && <p className="admin-error">{mutationError.message}</p>}
      <div className="admin-table-wrap">
        <table className="table admin-table">
          <thead>
            <tr>
              <th>User</th>
              <th>Joined</th>
              <th>Last seen</th>
              <th className="num">Msgs</th>
              <th>Plan</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((u) => (
              <tr key={u.id}>
                <td>
                  <div className="admin-user-name">{u.username}</div>
                  <div className="admin-user-email mono">{u.email}</div>
                </td>
                <td className="admin-dim">{ago(u.created_at)}</td>
                <td className="admin-dim">{ago(u.last_login)}</td>
                <td className="num">{u.messages}</td>
                <td>
                  <button
                    className={'admin-plan' + (u.plus ? ' admin-plan-plus' : '')}
                    disabled={setPlus.isPending}
                    onClick={() => setPlus.mutate({ user_id: u.id, on: !u.plus })}
                    title={u.plus ? 'Revoke Plus' : 'Grant Plus'}
                  >
                    {u.plus ? 'PLUS' : 'free'}
                  </button>
                </td>
                <td className="admin-row-actions">
                  {u.id === me?.id ? (
                    <span className="admin-dim">you</span>
                  ) : confirmDelete === u.id ? (
                    <>
                      <button className="btn btn-danger btn-sm" disabled={remove.isPending} onClick={() => remove.mutate(u.id)}>
                        {remove.isPending ? 'Deleting…' : 'Delete for good'}
                      </button>
                      <button className="admin-link" onClick={() => setConfirmDelete(null)}>
                        cancel
                      </button>
                    </>
                  ) : (
                    <button className="admin-link" onClick={() => setConfirmDelete(u.id)}>
                      delete
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length === 0 && <p className="admin-empty">No users match.</p>}
    </section>
  )
}

// ── Bug reports ──────────────────────────────────────────────────────────

function ReportsPanel() {
  const qc = useQueryClient()
  const [openId, setOpenId] = useState<string | null>(null)
  const reports = useQuery({
    queryKey: ['admin', 'reports'],
    queryFn: () => api.get<{ reports: ReportSummary[] }>('/api/admin/bug-reports'),
  })
  const remove = useMutation({
    mutationFn: (id: string) => api.del(`/api/admin/bug-reports/${id}`),
    onSuccess: (_, id) => {
      if (openId === id) setOpenId(null)
      qc.invalidateQueries({ queryKey: ['admin'] })
    },
  })

  if (reports.isPending) return <p className="admin-empty">Loading reports…</p>
  if (reports.error) return <p className="admin-error">{reports.error.message}</p>
  if (reports.data.reports.length === 0) return <p className="admin-empty">No bug reports. Nice.</p>

  return (
    <section className="card admin-panel admin-reports">
      {remove.error && <p className="admin-error">{remove.error.message}</p>}
      {reports.data.reports.map((r) => (
        <article key={r.id} className={'admin-report' + (openId === r.id ? ' admin-report-open' : '')}>
          <button className="admin-report-head" onClick={() => setOpenId(openId === r.id ? null : r.id)}>
            <span className="admin-report-note">{r.note || <em>No description</em>}</span>
            <span className="admin-report-meta mono">
              {r.user_email} · {ago(r.at)} · {r.msg_count} msgs{r.app_version && ` · ${r.app_version}`}
            </span>
          </button>
          {openId === r.id && <ReportDetail id={r.id} onDelete={() => remove.mutate(r.id)} deleting={remove.isPending} />}
        </article>
      ))}
    </section>
  )
}

function ReportDetail({ id, onDelete, deleting }: { id: string; onDelete: () => void; deleting: boolean }) {
  const detail = useQuery({
    queryKey: ['admin', 'report', id],
    queryFn: () => api.get<{ report: FullReport }>(`/api/admin/bug-reports/${id}`),
  })

  if (detail.isPending) return <p className="admin-empty">Loading…</p>
  if (detail.error) return <p className="admin-error">{detail.error.message}</p>

  const r = detail.data.report
  return (
    <div className="admin-report-body">
      {r.messages.length > 0 ? (
        <ol className="admin-transcript">
          {r.messages.map((m, i) => (
            <li key={i} className={'admin-transcript-' + m.role}>
              <span className="admin-transcript-role mono">{m.role === 'user' ? 'user' : 'paula'}</span>
              <span className="admin-transcript-text">{m.content}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="admin-dim">No chat attached.</p>
      )}
      <p className="admin-report-ua mono">{r.user_agent}</p>
      <button className="btn btn-danger btn-sm" onClick={onDelete} disabled={deleting}>
        {deleting ? 'Deleting…' : 'Delete report'}
      </button>
    </div>
  )
}

// ── Maintenance ──────────────────────────────────────────────────────────

function MaintenancePanel({ current }: { current: { on: boolean; message: string } }) {
  const qc = useQueryClient()
  const [message, setMessage] = useState(current.message)

  const save = useMutation({
    mutationFn: (on: boolean) => api.post('/api/admin/maintenance', { on, message }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'stats'] }),
  })

  return (
    <section className="card admin-panel admin-maint">
      <p className="admin-dim">
        Takes the app offline for everyone except you. Open sessions flip instantly over the websocket.
      </p>
      <label className="admin-maint-label" htmlFor="maint-msg">
        Message shown to users
      </label>
      <input
        id="maint-msg"
        className="input admin-filter"
        placeholder="Back in about 15 minutes."
        value={message}
        maxLength={300}
        onChange={(e) => setMessage(e.target.value)}
      />
      <div className="admin-maint-actions">
        {current.on ? (
          <>
            <button className="btn btn-primary" disabled={save.isPending} onClick={() => save.mutate(false)}>
              Bring the app back
            </button>
            <button className="admin-link" disabled={save.isPending} onClick={() => save.mutate(true)}>
              update message
            </button>
          </>
        ) : (
          <button className="btn btn-danger btn-sm" disabled={save.isPending} onClick={() => save.mutate(true)}>
            Turn maintenance on
          </button>
        )}
      </div>
      {save.error && <p className="admin-error">{save.error.message}</p>}
    </section>
  )
}
