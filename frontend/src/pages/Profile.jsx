import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useToast } from '../toast.jsx'
import { Badge, ErrorNote } from '../components/ui.jsx'
import { IconCopy, IconInfo } from '../components/icons.jsx'

function initials(name = '') {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return '?'
  return (parts[0][0] + (parts[1]?.[0] || '')).toUpperCase()
}

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric', month: 'long', day: 'numeric',
  })
}

export default function Profile() {
  const { user } = useAuth()
  const { push } = useToast()
  const [me, setMe] = useState(null)
  const [team, setTeam] = useState(null)
  const [count, setCount] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api('/api/auth/me').then(setMe).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!me) return
    if (me.role === 'team' && me.team_id) {
      api(`/api/teams/${me.team_id}`).then(setTeam).catch(() => {})
    }
    // real, existing endpoints per role
    if (me.role === 'citizen') {
      api('/api/problems').then((ps) => setCount(ps.length)).catch(() => {})
    } else if (me.role === 'team') {
      api('/api/teams/my-recommendations').then((rs) => setCount(rs.length)).catch(() => {})
    } else if (me.role === 'admin') {
      api('/api/stats/summary').then((s) => setCount(s.total_problems)).catch(() => {})
    }
  }, [me])

  function copy(text, what) {
    navigator.clipboard?.writeText(text).then(
      () => push(`${what} copied to clipboard`),
      () => push(`Could not copy ${what.toLowerCase()}`, 'error')
    )
  }

  if (!me) {
    return (
      <div className="page-loading">
        <span className="spinner" /> Loading profile…
        <ErrorNote msg={error} />
      </div>
    )
  }

  const av = initials(me.name)

  return (
    <>
      <div className="page-head">
        <div>
          <h1>My Profile</h1>
        </div>
        <Badge tone="violet" className="role">{me.role}</Badge>
      </div>

      <div className="card profile-hero">
        <div className="profile-avatar" aria-hidden="true">{av}</div>
        <div>
          <p className="profile-name">
            {me.name} <Badge tone={me.role === 'admin' ? 'red' : me.role === 'team' ? 'violet' : 'blue'}>{me.role}</Badge>
          </p>
          <p className="profile-email">{me.email}</p>
        </div>
      </div>

      <div className="profile-grid">
        <div className="card">
          <h3>Account</h3>
          <div className="profile-field">
            <span className="pf-label">Full name</span>
            <span className="pf-value">{me.name}</span>
          </div>
          <div className="profile-field">
            <span className="pf-label">Email</span>
            <span className="pf-value">
              {me.email}
              <button className="copy-btn" onClick={() => copy(me.email, 'Email')} title="Copy email"><IconCopy size={13} /> copy</button>
            </span>
          </div>
          <div className="profile-field">
            <span className="pf-label">Role</span>
            <span className="pf-value">{me.role}</span>
          </div>
          <div className="profile-field">
            <span className="pf-label">Member since</span>
            <span className="pf-value">{fmtDate(me.created_at)}</span>
          </div>
          <div className="profile-field">
            <span className="pf-label">User ID</span>
            <span className="pf-value">
              #{me.id}
              <button className="copy-btn" onClick={() => copy(String(me.id), 'User ID')} title="Copy ID"><IconCopy size={13} /> copy</button>
            </span>
          </div>
        </div>

        <div className="card">
          <h3>Activity</h3>
          {count == null ? (
            <p className="muted"><span className="spinner" /> Loading…</p>
          ) : (
            <>
              <div className="profile-field">
                <span className="pf-label">
                  {me.role === 'citizen' ? 'Problems reported' : me.role === 'team' ? 'Team recommendations received' : 'Problems on the platform'}
                </span>
                <span className="pf-value">{count}</span>
              </div>
              <div className="profile-field">
                <span className="pf-label">Where to go next</span>
                <span className="pf-value">
                  {me.role === 'citizen' && (
                    <>
                      <Link className="profile-link" to="/dashboard">My Problems</Link>
                      {' · '}
                      <Link className="profile-link" to="/submit">Submit a problem</Link>
                    </>
                  )}
                  {me.role === 'team' && (
                    <>
                      <Link className="profile-link" to="/team">Team Home</Link>
                      {' · '}
                      <Link className="profile-link" to="/team/recommended">Recommended</Link>
                    </>
                  )}
                  {me.role === 'admin' && (
                    <Link className="profile-link" to="/admin">Admin Dashboard</Link>
                  )}
                </span>
              </div>
            </>
          )}
          <div className="profile-note" style={{ marginTop: 14 }}>
            <span aria-hidden="true"><IconInfo size={16} /></span>
            <span>
              Editing name, password or adding a profile photo needs a user-update API endpoint.
              This build is UI-only and the backend contract is unchanged, so account details
              are shown here read-only.
            </span>
          </div>
        </div>

        {me.role === 'team' && (
          <div className="card">
            <h3>My team</h3>
            {team ? (
              <>
                <div className="profile-field">
                  <span className="pf-label">Team name</span>
                  <span className="pf-value">{team.name}</span>
                </div>
                <div className="profile-field">
                  <span className="pf-label">Skills</span>
                  <span className="pf-value" style={{ textTransform: 'none' }}>{(team.skills || []).join(', ') || '—'}</span>
                </div>
                <div className="profile-field">
                  <span className="pf-label">Experience</span>
                  <span className="pf-value" style={{ textTransform: 'none' }}>{team.experience || '—'}</span>
                </div>
                <div style={{ marginTop: 14 }}>
                  <Link to="/team" className="btn btn-primary btn-sm">
                    Open Team Home →
                  </Link>
                </div>
              </>
            ) : (
              <p className="muted">
                Team details are available on <Link to="/team">Team Home</Link>.
              </p>
            )}
          </div>
        )}
      </div>
    </>
  )
}
