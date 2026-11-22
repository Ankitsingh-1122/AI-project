import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import TeamMessages from '../components/TeamMessages.jsx'
import { Badge, ErrorNote, Spinner } from '../components/ui.jsx'
import { IconAward, IconEdit, IconHeart, IconInfo, IconSliders, IconTarget, IconUsers } from '../components/icons.jsx'

function initials(name = '') {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return '?'
  return (parts[0][0] + (parts[1]?.[0] || '')).toUpperCase()
}

export default function TeamDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const [team, setTeam] = useState(null)
  const [me, setMe] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api(`/api/teams/${id}`).then(setTeam).catch((e) => setError(e.message))
    api('/api/auth/me').then(setMe).catch(() => {})
  }, [id])

  if (error && !team) return <ErrorNote>{error}</ErrorNote>
  if (!team) return <Spinner label="Loading team profile…" />

  const isOwner = me && me.role === 'team' && me.team_id === team.id
  const isAdmin = user && user.role === 'admin'
  const members = team.members || []

  return (
    <>
      <div className="page-head">
        <div>
          <p className="muted">
            <Link to="/teams">← back to teams directory</Link>
          </p>
          <h1>{team.team_name}</h1>
        </div>
        {(isOwner || isAdmin) && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {isOwner && (
              <Link to="/team" className="btn btn-primary btn-sm"><IconEdit size={14} /> Edit team profile</Link>
            )}
            {isOwner && (
              <Link to="/team/recommended" className="btn btn-outline btn-sm"><IconTarget size={14} /> View recommendations</Link>
            )}
          </div>
        )}
      </div>

      <div className="card team-detail-hero">
        <div className="team-detail-avatar" aria-hidden="true"><IconUsers size={34} /></div>
        <div style={{ flex: 1, minWidth: 240 }}>
          <p style={{ margin: '0 0 6px' }}>{team.description || 'No description yet.'}</p>
          {team.experience && (
            <p className="muted small" style={{ margin: 0 }}><IconAward size={14} /> {team.experience}</p>
          )}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Badge tone="violet">{team.skills.length} skills</Badge>
          <Badge tone="gray">{members.length} members</Badge>
        </div>
      </div>

      <div className="profile-grid">
        <div className="card">
          <h3>Team members</h3>
          {members.length === 0 ? (
            <p className="muted">No members registered yet.</p>
          ) : (
            <div className="member-list">
              {members.map((m, i) => (
                <div className="member-item" key={m.id || i}>
                  <span className="member-avatar" aria-hidden="true">{initials(m.name)}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="member-name">{m.name}</div>
                  </div>
                  <Badge tone={m.role && m.role.toLowerCase() === 'lead' ? 'violet' : 'gray'}>
                    {m.role || 'member'}
                  </Badge>
                </div>
              ))}
            </div>
          )}
          <div className="profile-note" style={{ marginTop: 14 }}>
            <span aria-hidden="true"><IconInfo size={16} /></span>
            <span>
              The team profile stores each member&apos;s name and role. Messaging with this
              team is shared — one conversation for everyone, in the thread below.
            </span>
          </div>
        </div>

        <div className="card">
          <h3>Skills &amp; interests</h3>
          <h4 style={{ marginTop: 4 }}>Skills</h4>
          <div className="kw-row">
            {team.skills.map((s) => (
              <span className="kw" key={`s-${s}`}><IconSliders size={12} /> {s}</span>
            ))}
          </div>
          <h4 style={{ marginTop: 14 }}>Interests</h4>
          <div className="kw-row">
            {team.interests.map((s) => (
              <span className="kw kw-interest" key={`i-${s}`}><IconHeart size={12} /> {s}</span>
            ))}
          </div>
          <h4 style={{ marginTop: 14 }}>About</h4>
          <div className="profile-field">
            <span className="pf-label">Team ID</span>
            <span className="pf-value">#{team.id}</span>
          </div>
          <div className="profile-field">
            <span className="pf-label">Registered</span>
            <span className="pf-value">
              {team.created_at ? new Date(team.created_at).toLocaleDateString() : '—'}
            </span>
          </div>
        </div>
      </div>

      <TeamMessages teamId={team.id} teamName={team.team_name} />
    </>
  )
}
