import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useToast } from '../toast.jsx'
import { Badge, Empty, ErrorNote, LocationButton, ScoreBar, Spinner } from '../components/ui.jsx'
import { IconCheck, IconCpu, IconMapPin, IconThumbsDown, IconThumbsUp, IconX } from '../components/icons.jsx'

export default function TeamRecommended() {
  const { user } = useAuth()
  const toast = useToast()
  const [recs, setRecs] = useState(null)
  const [noTeam, setNoTeam] = useState(false)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('suggested')

  useEffect(() => {
    load()
  }, [])

  async function load() {
    try {
      const me = await api('/api/auth/me')
      if (!me.team_id) {
        // No team on this account (e.g. admin browsing) — show a clear
        // empty state instead of waiting forever.
        setNoTeam(true)
        setRecs([])
        return
      }
      const data = await api('/api/teams/my-recommendations')
      setRecs(data)
    } catch (err) {
      if (err.status !== 401) setError(err.message)
    }
  }

  async function decide(matchId, status) {
    const newStatus = status === 'accept' ? 'accepted' : 'rejected'
    // Optimistic move: the card jumps to its new tab instantly…
    setRecs((prev) => prev.map((r) => (r.match_id === matchId ? { ...r, match_status: newStatus } : r)))
    try {
      const r = await api(`/api/teams/matches/${matchId}/decision`, { method: 'POST', body: { status } })
      toast.push(
        status === 'accept'
          ? `Problem accepted — status is now “${r.problem_status}”`
          : 'Recommendation rejected'
      )
      await load()
    } catch (err) {
      if (err.status !== 401) setError(err.message)
    }
  }

  async function feedback(matchId, type) {
    try {
      await api('/api/feedback', { method: 'POST', body: { feedback_type: type, match_id: matchId } })
      toast.push(`Feedback recorded: ${type === 'good_match' ? 'good rec' : 'bad rec'}`)
    } catch (err) {
      if (err.status !== 401) toast.push(`Feedback error: ${err.message}`, 'error')
    }
  }

  if (error && !recs) return <ErrorNote>{error}</ErrorNote>
  if (!recs) return <Spinner />
  if (recs.length === 0)
    return (
      <div>
        <div className="page-head">
          <h1>Recommended for your team</h1>
        </div>
        <Empty>
          {noTeam
            ? <>This account isn't associated with a team, so there are no team recommendations to show here.{' '}
              {user.role === 'admin'
                ? <>You can browse every team in the <Link to="/teams">Teams Directory</Link>.</>
                : <>Once you register a <Link to="/team">team profile</Link>, matching problems will appear here.</>}
            </>
            : <>No recommendations yet. Make sure your <Link to="/team">team profile</Link> is registered
              with skills and interests.</>}
        </Empty>
      </div>
    )

  // A problem can generate more than one match row for the same team
  // (near-duplicate reports, re-computes). Once the team has DECIDED on any
  // match of a problem, the remaining "suggested" rows for that same problem
  // are retired from the Suggested tab — accepting one should remove the
  // problem from the queue. The same applies to near-duplicate reports with
  // an identical title (the API lists them as separate problems). They stay
  // visible under the "All" tab.
  const decided = recs.filter((r) => r.match_status !== 'suggested')
  const decidedProblems = new Set(decided.map((r) => r.problem_id))
  const decidedTitles = new Set(
    decided.map((r) => (r.title || '').toLowerCase().trim()).filter(Boolean)
  )

  const visible = recs.filter((r) => {
    if (filter !== 'all' && r.match_status !== filter) return false
    if (r.match_status === 'suggested' && filter !== 'all') {
      if (decidedProblems.has(r.problem_id)) return false
      if (decidedTitles.has((r.title || '').toLowerCase().trim())) return false
    }
    return true
  })

  return (
    <div>
      <div className="page-head">
        <h1>Recommended for your team</h1>
        <div className="filters" style={{ margin: 0 }}>
          {['suggested', 'accepted', 'rejected', 'all'].map((f) => (
            <button key={f} className={`chip ${filter === f ? 'active' : ''}`} onClick={() => setFilter(f)}>
              {f}
            </button>
          ))}
        </div>
      </div>

      <ErrorNote>{error}</ErrorNote>

      <div className="card-list">
        {visible.length === 0 && <Empty>Nothing in this filter.</Empty>}
        {visible.map((r) => (
          <div className="card rec-card" key={r.match_id}>
            <div className="card-top">
              <Link to={`/problem/${r.problem_id}`}><h3>{r.title}</h3></Link>
              <div className="card-badges">
                <Badge tone={r.match_status === 'accepted' ? 'green' : r.match_status === 'rejected' ? 'red' : 'blue'}>
                  {r.match_status}
                </Badge>
                <Badge tone="gray">{r.category}</Badge>
              </div>
            </div>
            <p className="card-text">{r.description}</p>
            <div className="note note-info">
              <b>Why you:</b> {r.explanation}
            </div>
            <div className="card-meta">
              {r.location && <span className="meta-item"><IconMapPin size={14} /> {r.location}</span>}
              <span className="meta-item"><IconCpu size={14} /> relevance</span>
              <ScoreBar value={r.score} label />
              <LocationButton location={r.location} small label="View Live Location" />
            </div>
            {r.match_status === 'suggested' && (
              <div className="rec-actions">
                <button className="btn btn-primary btn-sm" onClick={() => decide(r.match_id, 'accept')}>
                  <IconCheck size={14} /> Accept problem
                </button>
                <button className="btn btn-ghost btn-sm" onClick={() => decide(r.match_id, 'reject')}>
                  <IconX size={14} /> Not for us
                </button>
                <span className="fb-buttons">
                  <button className="btn btn-ghost btn-sm" onClick={() => feedback(r.match_id, 'good_match')}><IconThumbsUp size={13} /> good rec</button>
                  <button className="btn btn-ghost btn-sm" onClick={() => feedback(r.match_id, 'bad_match')}><IconThumbsDown size={13} /> bad rec</button>
                </span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
