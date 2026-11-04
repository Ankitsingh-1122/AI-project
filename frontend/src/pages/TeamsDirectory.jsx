import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useToast } from '../toast.jsx'
import { Badge, Empty, ErrorNote, Spinner } from '../components/ui.jsx'

export default function TeamsDirectory() {
  const { user } = useAuth()
  const toast = useToast()
  const isAdmin = user?.role === 'admin'
  const [teams, setTeams] = useState(null)
  const [error, setError] = useState('')
  const [q, setQ] = useState('')
  const [deleting, setDeleting] = useState(null)

  useEffect(() => {
    load()
  }, [])

  async function load() {
    try {
      setTeams(await api('/api/teams'))
    } catch (err) {
      if (err.status !== 401) setError(err.message)
    }
  }

  async function onDelete(t) {
    const ok = window.confirm(
      `Delete team “${t.team_name}”?\n\n` +
        'This removes the team from the directory, its members and any pending matches. ' +
        'The team will be told when it next logs in. This cannot be undone.'
    )
    if (!ok) return
    setDeleting(t.id)
    try {
      await api(`/api/teams/${t.id}`, { method: 'DELETE' })
      toast.push(`🗑 Team “${t.team_name}” removed from the directory`)
      await load()
      window.dispatchEvent(new Event('civic-notifications'))
    } catch (err) {
      toast.push('⚠️ Could not delete team: ' + err.message)
    } finally {
      setDeleting(null)
    }
  }

  if (error) return <ErrorNote>{error}</ErrorNote>
  if (!teams) return <Spinner />

  const visible = teams.filter((t) => {
    if (!q) return true
    const hay = `${t.team_name} ${t.description} ${t.skills.join(' ')} ${t.interests.join(' ')}`.toLowerCase()
    return hay.includes(q.toLowerCase())
  })

  return (
    <div>
      <div className="page-head">
        <h1>Student teams</h1>
        <input
          className="search-input"
          placeholder="🔍 search by skill or interest…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>
      <p className="muted">
        These teams are matched to citizen problems by skills, interests and experience.
      </p>

      {visible.length === 0 ? (
        <Empty>No teams match your search.</Empty>
      ) : (
        <div className="teams-grid">
          {visible.map((t) => (
            <div className="team-card-slot" key={t.id}>
              <Link to={`/teams/${t.id}`} className="team-card-link">
              <div className="card team-card">
                <div className="card-top">
                  <h3>{t.team_name}</h3>
                  <Badge tone="violet">{t.skills.length} skills</Badge>
                </div>
                <p className="card-text">{t.description}</p>
                <div className="kw-row">
                  {t.skills.map((s) => (
                    <span className="kw" key={`s-${s}`}>⚙ {s}</span>
                  ))}
                </div>
                <div className="kw-row">
                  {t.interests.map((s) => (
                    <span className="kw kw-interest" key={`i-${s}`}>❤ {s}</span>
                  ))}
                </div>
                {t.experience && (
                  <p className="muted small" style={{ marginTop: 8 }}>
                    🏆 {t.experience}
                  </p>
                )}
                <p className="small" style={{ marginTop: 10, fontWeight: 700, color: 'var(--primary)' }}>
                  View team profile & members →
                </p>
              </div>
              </Link>
              {isAdmin && (
                <button
                  className="team-delete-btn"
                  title={deleting === t.id ? 'Deleting…' : 'Delete team (admin only)'}
                  aria-label={`Delete team ${t.team_name}`}
                  disabled={deleting === t.id}
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    onDelete(t)
                  }}
                >
                  {deleting === t.id ? '…' : '🗑'}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
