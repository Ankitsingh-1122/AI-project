import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useToast } from '../toast.jsx'
import TeamMessages from '../components/TeamMessages.jsx'
import { ErrorNote } from '../components/ui.jsx'
import { IconCheck, IconChevronRight, IconCpu, IconHeart, IconLogout, IconPlus, IconSliders, IconUsers, IconX } from '../components/icons.jsx'

const emptyTeam = {
  team_name: '',
  description: '',
  skills: '',
  interests: '',
  experience: '',
  members: [{ name: '', role: 'member' }]
}

export const MAX_TEAM_MEMBERS = 10

export default function TeamDashboard() {
  const { user } = useAuth()
  const toast = useToast()
  const [team, setTeam] = useState(null)
  const [form, setForm] = useState(emptyTeam)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [deletedNote, setDeletedNote] = useState(null)
  const [bannerHidden, setBannerHidden] = useState(false)
  const [assignedProblems, setAssignedProblems] = useState([])
  const [inProgressProblems, setInProgressProblems] = useState([])

  useEffect(() => {
    load()
  }, [])

  async function load() {
    try {
      const me = await api('/api/auth/me')
      if (me.team_id) {
        const [t, recs] = await Promise.all([
          api(`/api/teams/${me.team_id}`),
          api('/api/teams/my-recommendations').catch(() => [])
        ])
        setTeam(t)
        const pending = (recs || []).filter(
          (r) => r.match_status === 'assigned' && r.status !== 'resolved'
        )
        setAssignedProblems(pending)
        const active = (recs || []).filter(
          (r) => r.match_status === 'accepted' && r.status !== 'resolved'
        )
        setInProgressProblems(active)
        setForm({
          team_name: t.team_name,
          description: t.description,
          skills: t.skills.join(', '),
          interests: t.interests.join(', '),
          experience: t.experience,
          members: t.members.length
            ? t.members.map((m) => ({ name: m.name, role: m.role }))
            : [{ name: '', role: 'member' }]
        })
      } else {
        // No team right now — if an admin removed one, say so properly.
        const notes = await api('/api/notifications')
        const removed = notes.find((n) => n.type === 'team_deleted')
        setDeletedNote(removed || null)
      }
    } catch (err) {
      if (err.status !== 401) setError(err.message)
    }
  }

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  function setMember(i, field, value) {
    setForm((f) => ({
      ...f,
      members: f.members.map((m, j) => (j === i ? { ...m, [field]: value } : m))
    }))
  }

  function addMember() {
    setForm((f) => ({ ...f, members: [...f.members, { name: '', role: 'member' }] }))
  }

  function removeMember(i) {
    setForm((f) => ({ ...f, members: f.members.filter((_, j) => j !== i) }))
  }

  async function save(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    const body = {
      team_name: form.team_name,
      description: form.description,
      skills: form.skills.split(',').map((s) => s.trim()).filter(Boolean),
      interests: form.interests.split(',').map((s) => s.trim()).filter(Boolean),
      experience: form.experience,
      members: form.members.filter((m) => m.name.trim())
    }
    try {
      if (team) {
        await api(`/api/teams/${team.id}`, { method: 'PUT', body })
      } else {
        await api('/api/teams', { method: 'POST', body })
      }
      toast.push('Saved. Your team details are up to date.')
      await load()
    } catch (err) {
      if (err.status !== 401) setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const previewText = [
    form.team_name,
    form.description,
    form.skills,
    form.interests,
    form.experience
  ]
    .filter(Boolean)
    .join(' . ')

  return (
    <div>
      <div className="page-head">
        <h1>My Team</h1>
        <Link to="/team/recommended" className="btn btn-primary btn-lg">
          See suggested problems
          {assignedProblems.length > 0 && (
            <span className="badge badge-amber" style={{ marginLeft: 8, padding: '2px 8px', borderRadius: '12px' }}>
              {assignedProblems.length} new
            </span>
          )}
          <IconChevronRight size={20} />
        </Link>
      </div>

      {assignedProblems.length > 0 && (
        <div className="card note note-info" style={{ marginBottom: 20, borderLeft: '4px solid var(--warn, #f59e0b)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: '1.05rem', color: 'var(--warn, #f59e0b)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <IconCpu size={20} /> {assignedProblems.length} Problem{assignedProblems.length > 1 ? 's' : ''} Assigned by AI to Your Team
              </div>
              <p style={{ margin: '6px 0 0 0' }}>
                Latest: <b>{assignedProblems[0].title}</b> ({Math.round((assignedProblems[0].score ?? 0) * 100)}% fit match)
              </p>
            </div>
            <Link to="/team/recommended" className="btn btn-primary">
              Review & Accept <IconChevronRight size={18} />
            </Link>
          </div>
        </div>
      )}

      {inProgressProblems.length > 0 && (
        <div className="card" style={{ marginBottom: 20, borderLeft: '4px solid #16a34a' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8, color: '#16a34a' }}>
              <IconCheck size={20} /> Active Projects ({inProgressProblems.length} In Progress)
            </h3>
            <Link to="/team/recommended" className="btn btn-ghost btn-sm">
              View all <IconChevronRight size={16} />
            </Link>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {inProgressProblems.map((pr) => (
              <div key={pr.problem_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, padding: '10px 14px', background: 'var(--hover-bg, #f8fafc)', borderRadius: 8 }}>
                <div>
                  <Link to={`/problem/${pr.problem_id}`} style={{ fontWeight: 600 }}>#{pr.problem_id} · {pr.title}</Link>
                  <div style={{ fontSize: '0.8rem', color: 'var(--muted, #64748b)' }}>{pr.location || 'Location not specified'}</div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    className="btn btn-primary btn-sm"
                    style={{ background: '#16a34a', borderColor: '#16a34a' }}
                    onClick={async () => {
                      try {
                        await api(`/api/problems/${pr.problem_id}`, { method: 'PUT', body: { status: 'resolved' } })
                        toast.push('Problem marked as completed!')
                        load()
                      } catch (e) {
                        toast.push(`Error: ${e.message}`, 'error')
                      }
                    }}
                  >
                    <IconCheck size={16} /> Mark Completed
                  </button>
                  <Link to={`/problem/${pr.problem_id}`} className="btn btn-outline btn-sm">
                    Details
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <ErrorNote>{error}</ErrorNote>

      {!team && deletedNote && !bannerHidden && (
        <div className="note note-danger team-deleted-banner">
          <span className="tdb-ico" aria-hidden="true"><IconLogout size={22} /></span>
          <div className="tdb-body">
            <b>Your team was removed by an administrator.</b>
            <div className="tdb-text">{deletedNote.body}</div>
            <div className="muted small">You can register a new team using the form below.</div>
          </div>
          <button
            className="tdb-close"
            aria-label="Dismiss"
            title="Dismiss (the record stays in your notifications)"
            onClick={() => setBannerHidden(true)}
          >
            <IconX size={16} />
          </button>
        </div>
      )}

      {!team && (
        <div className="note note-info">
          Fill in your team’s details below and press “Register team”. We use your team name, what you do,
          your skills and interests to suggest problems that suit you.
        </div>
      )}

      <div className="team-grid">
        <form className="card form" onSubmit={save}>
          <div className="form-grid">
            <label>Team name
              <input value={form.team_name} onChange={(e) => set('team_name', e.target.value)} required minLength={2} />
            </label>
            <label>Past projects <span className="hint">What has your team done before?</span>
              <input value={form.experience} onChange={(e) => set('experience', e.target.value)}
                placeholder="e.g. Built a street light monitoring app last year" />
            </label>
          </div>
          <label>About your team
            <textarea rows={3} value={form.description} onChange={(e) => set('description', e.target.value)}
              placeholder="What does your team do?" />
          </label>
          <label>Your skills <span className="hint">Separate with commas</span>
            <input value={form.skills} onChange={(e) => set('skills', e.target.value)}
              placeholder="python, computer vision, iot, data analysis" />
          </label>
          <label>Problems you like to work on <span className="hint">Separate with commas</span>
            <input value={form.interests} onChange={(e) => set('interests', e.target.value)}
              placeholder="street lights, potholes, water supply" />
          </label>

          <h2>
            Team members{' '}
            <span className={'member-count' + (form.members.length >= MAX_TEAM_MEMBERS ? ' at-cap' : '')}>
              {form.members.length}/{MAX_TEAM_MEMBERS}
            </span>
          </h2>
          <p className="muted member-cap-note">
            A team can have up to {MAX_TEAM_MEMBERS} members.
          </p>
          {form.members.map((m, i) => (
            <div className="member-row" key={i}>
              <input value={m.name} onChange={(e) => setMember(i, 'name', e.target.value)} placeholder="Name" aria-label="Member name" />
              <input value={m.role} onChange={(e) => setMember(i, 'role', e.target.value)} placeholder="Role" aria-label="Member role" className="role-input" />
              {form.members.length > 1 && (
                <button type="button" className="btn btn-outline" onClick={() => removeMember(i)} aria-label="Remove this member"><IconX size={18} /> Remove</button>
              )}
            </div>
          ))}
          <button
            type="button"
            className="btn btn-outline"
            onClick={addMember}
            disabled={form.members.length >= MAX_TEAM_MEMBERS}
            title={form.members.length >= MAX_TEAM_MEMBERS ? `Maximum ${MAX_TEAM_MEMBERS} members per team` : 'Add another member'}
          >
            <IconPlus size={18} /> Add a member
          </button>
          {form.members.length >= MAX_TEAM_MEMBERS && (
            <p className="muted" role="note">
              You have reached {MAX_TEAM_MEMBERS} members. Remove someone to add another.
            </p>
          )}

          <button className="btn btn-primary btn-lg" disabled={busy}>
            {busy ? 'Saving…' : team ? 'Save changes' : 'Register team'}
          </button>
        </form>

        <details className="card tech-details">
          <summary>How we describe your team (technical)</summary>
          <p className="muted">
            This text is compared with every reported problem to find a good fit:
          </p>
          <div className="team-preview">
            {previewText || 'Start typing to see your team profile text…'}
          </div>
          <div className="kw-row" style={{ marginTop: 12 }}>
            {form.skills.split(',').map((s) => s.trim()).filter(Boolean).map((s) => (
              <span className="kw" key={`s-${s}`}><IconSliders size={14} /> {s}</span>
            ))}
            {form.interests.split(',').map((s) => s.trim()).filter(Boolean).map((s) => (
              <span className="kw kw-interest" key={`i-${s}`}><IconHeart size={14} /> {s}</span>
            ))}
          </div>
          {team && (
            <div className="card-meta">
              <span className="meta-item"><IconUsers size={18} /> {team.members.length} members</span>
              <span className="meta-item"><IconCpu size={18} /> team id: {team.id}</span>
            </div>
          )}
        </details>
      </div>

      {team && (
        <div style={{ marginTop: 16 }}>
          <TeamMessages teamId={team.id} teamName={team.team_name} />
        </div>
      )}
    </div>
  )
}
