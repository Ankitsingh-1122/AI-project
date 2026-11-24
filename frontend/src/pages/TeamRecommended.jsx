import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useToast } from '../toast.jsx'
import { Badge, Empty, ErrorNote, LocationButton, Spinner } from '../components/ui.jsx'
import { IconCheck, IconMapPin, IconThumbsDown, IconThumbsUp, IconX } from '../components/icons.jsx'

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
          ? 'Problem accepted — your team is now working on it'
          : 'Declined — administrator has been alerted to reassign'
      )
      await load()
    } catch (err) {
      if (err.status !== 401) setError(err.message)
    }
  }

  async function markResolved(problemId) {
    try {
      await api(`/api/problems/${problemId}`, { method: 'PUT', body: { status: 'resolved' } })
      toast.push('Problem marked as completed! Great job.')
      await load()
    } catch (err) {
      if (err.status !== 401) toast.push(`Could not update problem: ${err.message}`, 'error')
    }
  }

  async function feedback(matchId, type) {
    try {
      await api('/api/feedback', { method: 'POST', body: { feedback_type: type, match_id: matchId } })
      toast.push(type === 'good_match' ? 'Thank you — noted as a good suggestion' : 'Thank you — noted as a poor suggestion')
    } catch (err) {
      if (err.status !== 401) toast.push(`Could not send your feedback: ${err.message}`, 'error')
    }
  }

  if (error && !recs) return <ErrorNote>{error}</ErrorNote>
  if (!recs) return <Spinner />
  if (recs.length === 0)
    return (
      <div>
        <div className="page-head">
          <h1>Suggested Problems</h1>
        </div>
        <Empty>
          {noTeam
            ? <>This account isn't associated with a team, so there are no team recommendations to show here.{' '}
              {user.role === 'admin'
                ? <>You can browse every team in the <Link to="/teams">All Teams page</Link>.</>
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
  const isPending = (s) => s === 'suggested' || s === 'assigned'
  const decided = recs.filter((r) => !isPending(r.match_status))
  const decidedProblems = new Set(decided.map((r) => r.problem_id))
  const decidedTitles = new Set(
    decided.map((r) => (r.title || '').toLowerCase().trim()).filter(Boolean)
  )

  const visible = recs.filter((r) => {
    if (filter === 'suggested') {
      if (!isPending(r.match_status)) return false
    } else if (filter !== 'all' && r.match_status !== filter) {
      return false
    }
    if (isPending(r.match_status) && filter !== 'all') {
      if (decidedProblems.has(r.problem_id)) return false
      if (decidedTitles.has((r.title || '').toLowerCase().trim())) return false
      if (r.status === 'resolved') return false
      if (r.match_status === 'suggested' && r.status === 'assigned') return false
    }
    return true
  })

  // Ensure assigned problems always come first, followed by newest created_at / highest score
  const sorted = [...visible].sort((a, b) => {
    if (a.match_status === 'assigned' && b.match_status !== 'assigned') return -1
    if (b.match_status === 'assigned' && a.match_status !== 'assigned') return 1
    const tA = new Date(a.created_at || 0).getTime()
    const tB = new Date(b.created_at || 0).getTime()
    if (tB !== tA) return tB - tA
    return (b.score || 0) - (a.score || 0)
  })

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Suggested Problems</h1>
          <p className="page-sub">Problems that fit your team’s skills. Accept the ones you want to work on.</p>
        </div>
        <div className="seg" role="group" aria-label="Show">
          {[['suggested', 'New / Assigned'], ['accepted', 'Accepted'], ['rejected', 'Declined'], ['all', 'All']].map(([f, label]) => (
            <button key={f} type="button" className={'seg-btn' + (filter === f ? ' active' : '')}
              aria-pressed={filter === f} onClick={() => setFilter(f)}>
              {label}
            </button>
          ))}
        </div>
      </div>

      <ErrorNote>{error}</ErrorNote>

      <div className="card-list">
        {sorted.length === 0 && <Empty>Nothing here right now.</Empty>}
        {sorted.map((r) => (
          <div className="card rec-card" key={r.match_id}>
            <div className="card-top">
              <Link to={`/problem/${r.problem_id}`}><h3>{r.title}</h3></Link>
              <div className="card-badges">
                <Badge tone={r.match_status === 'accepted' ? 'green' : r.match_status === 'rejected' ? 'red' : r.match_status === 'assigned' ? 'amber' : 'blue'}>
                  {r.match_status === 'accepted' ? 'Accepted' : r.match_status === 'rejected' ? 'Declined' : r.match_status === 'assigned' ? 'AI Assigned' : 'New'}
                </Badge>
                <Badge tone="gray">{(r.category || '').replace(/_/g, ' ')}</Badge>
              </div>
            </div>
            <p className="card-text">{r.description}</p>
            <div className="note note-info">
              <b>Why this fits your team:</b> {r.explanation}
            </div>
            <div className="card-meta">
              {r.location && <span className="meta-item"><IconMapPin size={18} /> {r.location}</span>}
              <span className="meta-item">Fit: <b>{Math.round((r.score ?? 0) * 100)}%</b></span>
              <LocationButton location={r.location} />
            </div>
            {(r.match_status === 'suggested' || r.match_status === 'assigned') && (
              <div className="rec-actions">
                <button className="btn btn-primary" onClick={() => decide(r.match_id, 'accept')}>
                  <IconCheck size={20} /> Accept this problem
                </button>
                <button className="btn btn-outline" onClick={() => decide(r.match_id, 'reject')}>
                  <IconX size={20} /> Not for us
                </button>
                <span className="fb-buttons">
                  <button className="btn btn-ghost" onClick={() => feedback(r.match_id, 'good_match')}><IconThumbsUp size={18} /> Good suggestion</button>
                  <button className="btn btn-ghost" onClick={() => feedback(r.match_id, 'bad_match')}><IconThumbsDown size={18} /> Poor suggestion</button>
                </span>
              </div>
            )}
            {r.match_status === 'accepted' && (
              <div className="rec-actions" style={{ marginTop: 14, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                {r.status === 'resolved' ? (
                  <span className="badge badge-green" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 12px', fontSize: '0.9rem' }}>
                    <IconCheck size={16} /> Completed / Solved
                  </span>
                ) : (
                  <button
                    className="btn btn-primary"
                    style={{ background: '#16a34a', borderColor: '#16a34a' }}
                    onClick={() => markResolved(r.problem_id)}
                  >
                    <IconCheck size={18} /> Mark as Completed
                  </button>
                )}
                <Link to={`/problem/${r.problem_id}`} className="btn btn-outline">
                  View Report Details
                </Link>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
