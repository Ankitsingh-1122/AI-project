import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useToast } from '../toast.jsx'
import TeamMessages from '../components/TeamMessages.jsx'
import { ErrorNote } from '../components/ui.jsx'
import { IconChevronRight, IconCpu, IconHeart, IconLogout, IconPlus, IconSliders, IconUsers, IconX } from '../components/icons.jsx'

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

  useEffect(() => {
    load()
  }, [])

  async function load() {
    try {
      const me = await api('/api/auth/me')
      if (me.team_id) {
        const t = await api(`/api/teams/${me.team_id}`)
        setTeam(t)
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
      toast.push('Team profile saved — matching now uses the new skills & interests')
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
        <h1>Team profile</h1>
        <Link to="/team/recommended" className="btn btn-outline">View recommendations <IconChevronRight size={14} /></Link>
      </div>

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
          Register your team below. The AI builds your team’s embedding from
          <b> name + description + skills + interests + experience</b>, then matches problems
          against it.
        </div>
      )}

      <div className="team-grid">
        <form className="card form" onSubmit={save}>
          <div className="form-grid">
            <label>Team name
              <input value={form.team_name} onChange={(e) => set('team_name', e.target.value)} required minLength={2} />
            </label>
            <label>Experience / past projects
              <input value={form.experience} onChange={(e) => set('experience', e.target.value)}
                placeholder="e.g. Built a street light monitoring app last year" />
            </label>
          </div>
          <label>Description
            <textarea rows={3} value={form.description} onChange={(e) => set('description', e.target.value)}
              placeholder="What does your team do?" />
          </label>
          <label>Technical skills (comma-separated)
            <input value={form.skills} onChange={(e) => set('skills', e.target.value)}
              placeholder="python, computer vision, iot, data analysis" />
          </label>
          <label>Areas of interest (comma-separated)
            <input value={form.interests} onChange={(e) => set('interests', e.target.value)}
              placeholder="street lights, potholes, water supply" />
          </label>

          <h3>
            Members{' '}
            <span className={'member-count' + (form.members.length >= MAX_TEAM_MEMBERS ? ' at-cap' : '')}>
              {form.members.length}/{MAX_TEAM_MEMBERS}
            </span>
          </h3>
          <p className="muted small member-cap-note">
            A team can have at most {MAX_TEAM_MEMBERS} members — pick your core squad.
          </p>
          {form.members.map((m, i) => (
            <div className="member-row" key={i}>
              <input value={m.name} onChange={(e) => setMember(i, 'name', e.target.value)} placeholder="Member name" />
              <input value={m.role} onChange={(e) => setMember(i, 'role', e.target.value)} placeholder="role" className="role-input" />
              {form.members.length > 1 && (
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => removeMember(i)} aria-label="Remove member"><IconX size={14} /></button>
              )}
            </div>
          ))}
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={addMember}
            disabled={form.members.length >= MAX_TEAM_MEMBERS}
            title={form.members.length >= MAX_TEAM_MEMBERS ? `Maximum ${MAX_TEAM_MEMBERS} members per team` : 'Add another member'}
          >
            <IconPlus size={14} /> Add member
          </button>
          {form.members.length >= MAX_TEAM_MEMBERS && (
            <p className="muted small" role="note">
              Maximum of {MAX_TEAM_MEMBERS} members reached — remove someone to add another.
            </p>
          )}

          <button className="btn btn-primary" disabled={busy}>
            {busy ? 'Saving…' : team ? 'Update team profile' : 'Register team'}
          </button>
        </form>

        <div className="card">
          <h3>AI sees your team as…</h3>
          <p className="muted small">
            This exact text is embedded and compared with every citizen problem:
          </p>
          <div className="team-preview">
            {previewText || 'Start typing to see your team profile text…'}
          </div>
          <div className="kw-row" style={{ marginTop: 12 }}>
            {form.skills.split(',').map((s) => s.trim()).filter(Boolean).map((s) => (
              <span className="kw" key={`s-${s}`}><IconSliders size={12} /> {s}</span>
            ))}
            {form.interests.split(',').map((s) => s.trim()).filter(Boolean).map((s) => (
              <span className="kw kw-interest" key={`i-${s}`}><IconHeart size={12} /> {s}</span>
            ))}
          </div>
          {team && (
            <div className="card-meta">
              <span className="meta-item"><IconUsers size={14} /> {team.members.length} members</span>
              <span className="meta-item"><IconCpu size={14} /> team id: {team.id}</span>
            </div>
          )}
        </div>
      </div>

      {team && (
        <div style={{ marginTop: 16 }}>
          <TeamMessages teamId={team.id} teamName={team.team_name} />
        </div>
      )}
    </div>
  )
}
