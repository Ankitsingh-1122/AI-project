import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useToast } from '../toast.jsx'
import { Badge, DuplicateBadge, ErrorNote, LocationButton, Select, Spinner, statusLabel, statusTone } from '../components/ui.jsx'
import { IconAlert, IconBox, IconCheck, IconClock, IconFileText, IconGraduationCap, IconMagnet, IconMapPin, IconRefresh, IconThumbsDown, IconThumbsUp, IconX } from '../components/icons.jsx'

export default function ProblemDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const toast = useToast()
  const [p, setP] = useState(null)
  const [analysis, setAnalysis] = useState(null)
  const [error, setError] = useState('')
  const [feedbackComment, setFeedbackComment] = useState('')
  const [showNlp, setShowNlp] = useState(false)

  useEffect(() => {
    load()
  }, [id])

  async function load() {
    try {
      const [problem, detail] = await Promise.all([
        api(`/api/problems/${id}`),
        api(`/api/ai/analysis/${id}`)
      ])
      setP(problem)
      setAnalysis(detail)
    } catch (err) {
      if (err.status !== 401) setError(err.message)
    }
  }

  async function sendFeedback(matchId, type) {
    try {
      await api('/api/feedback', {
        method: 'POST',
        body: {
          feedback_type: type,
          match_id: matchId,
          problem_id: Number(id),
          comment: feedbackComment
        }
      })
      toast.push(type === 'good_match' ? 'Thank you — marked as a good match' : 'Thank you — marked as not a good match')
      setFeedbackComment('')
    } catch (err) {
      if (err.status !== 401) toast.push(`Feedback error: ${err.message}`, 'error')
    }
  }

  async function sendDuplicateFeedback(correct) {
    try {
      await api('/api/feedback', {
        method: 'POST',
        body: {
          feedback_type: correct ? 'correct_duplicate' : 'wrong_duplicate',
          problem_id: Number(id),
          comment: feedbackComment
        }
      })
      toast.push(
        correct
          ? 'Thank you — we noted it is the same problem'
          : 'Thank you — we noted it is a different problem'
      )
      setFeedbackComment('')
    } catch (err) {
      if (err.status !== 401) toast.push(`Feedback error: ${err.message}`, 'error')
    }
  }

  async function toggleUpvote() {
    try {
      const res = await api(`/api/problems/${id}/upvote`, { method: 'POST' })
      setP((prev) => ({
        ...prev,
        upvotes: res.upvotes,
        user_upvoted: res.upvoted,
      }))
      toast.push(res.upvoted ? "Thank you! Upvoted as 'I am affected too'." : "Upvote removed.")
    } catch (err) {
      if (err.status !== 401) toast.push(`Could not update upvote: ${err.message}`, 'error')
    }
  }

  async function changeStatus(status) {
    try {
      const data = await api(`/api/problems/${id}`, { method: 'PUT', body: { status } })
      setP(data.problem)
      toast.push(`Status changed to “${statusLabel(status)}”`)
    } catch (err) {
      if (err.status !== 401) setError(err.message)
    }
  }

  if (error && !p) return <ErrorNote>{error}</ErrorNote>
  if (!p) return <Spinner />

  const isOwner = user && user.role === 'citizen' && p?.owner_id === user?.id
  const isAdmin = user && user.role === 'admin'
  const isAssignedTeam = user && user.role === 'team' && (
    (p?.assigned_team && p?.assigned_team?.id === user?.team_id) ||
    p?.recommended_teams?.some((t) => t.team_id === user?.team_id && (t.status === 'accepted' || t.status === 'assigned'))
  )
  const canChangeStatus = isAdmin || isOwner || isAssignedTeam
  const canEdit = isAdmin || isOwner
  const nlp = analysis?.nlp
  const topSimilar = p.similar?.[0]
  const topTeam = p.recommended_teams?.[0]
  const trainedDup = analysis?.duplicate?.method === 'trained_classifier'

  // If any team has accepted this problem, identify it as the single assigned team.
  // We hide the other suggested candidates and feedback buttons since the report is
  // already in progress with this team.
  const acceptedTeam = p.recommended_teams?.find((t) => t.status === 'accepted' || t.status === 'assigned') || (p.assigned_team ? {
    team_name: p.assigned_team.team_name,
    team_id: p.assigned_team.id,
    status: p.assigned_team.status || 'assigned'
  } : null)
  const hasAcceptedTeam = !!acceptedTeam

  return (
    <div>
      <div className="page-head">
        <div>
          <p className="muted">Report #{p.id}</p>
          <h1>{p.title}</h1>
        </div>
        <div className="card-badges">
          <Badge tone={statusTone(p.status)}>{statusLabel(p.status)}</Badge>
          {p.assigned_team && (
            <Badge tone="green">Team: {p.assigned_team.team_name}</Badge>
          )}
          <Badge tone="blue">{p.category.replace(/_/g, ' ')}</Badge>
          <DuplicateBadge p={p} />
        </div>
      </div>

      <ErrorNote>{error}</ErrorNote>

      {/* Visual Resolution Lifecycle Tracker */}
      <div className="card timeline-card" style={{ marginBottom: 20, padding: '18px 24px' }}>
        <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--muted, #64748b)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 14 }}>
          Resolution Lifecycle Progress
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', position: 'relative', gap: 8 }}>
          {/* Step 1: Reported */}
          <div style={{ flex: 1, textAlign: 'center' }}>
            <div style={{ width: 34, height: 34, borderRadius: '50%', background: '#16a34a', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 6px', fontWeight: 'bold' }}>✓</div>
            <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>Reported</div>
            <div style={{ fontSize: '0.72rem', color: 'var(--muted, #64748b)' }}>{p.created_at ? new Date(p.created_at).toLocaleDateString() : 'Logged'}</div>
          </div>

          <div style={{ height: 2, background: '#16a34a', flex: 0.5, marginTop: 17 }}></div>

          {/* Step 2: AI Triaged */}
          <div style={{ flex: 1, textAlign: 'center' }}>
            <div style={{ width: 34, height: 34, borderRadius: '50%', background: '#16a34a', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 6px', fontWeight: 'bold' }}>✓</div>
            <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>AI Triaged</div>
            <div style={{ fontSize: '0.72rem', color: 'var(--muted, #64748b)' }}>{p.cluster || 'Analyzed'}</div>
          </div>

          <div style={{ height: 2, background: p.status === 'assigned' || p.status === 'in_review' || p.status === 'resolved' ? '#16a34a' : 'var(--card-border, #e2e8f0)', flex: 0.5, marginTop: 17 }}></div>

          {/* Step 3: Team Assigned */}
          <div style={{ flex: 1, textAlign: 'center' }}>
            <div style={{
              width: 34, height: 34, borderRadius: '50%',
              background: p.status === 'assigned' || p.status === 'in_review' || p.status === 'resolved' ? '#16a34a' : '#f59e0b',
              color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 6px', fontWeight: 'bold'
            }}>
              {p.status === 'assigned' || p.status === 'in_review' || p.status === 'resolved' ? '✓' : '3'}
            </div>
            <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>Team Assigned</div>
            <div style={{ fontSize: '0.72rem', color: 'var(--muted, #64748b)' }}>
              {p.assigned_team?.team_name || acceptedTeam?.team_name || 'Matching'}
            </div>
          </div>

          <div style={{ height: 2, background: p.status === 'resolved' ? '#16a34a' : 'var(--card-border, #e2e8f0)', flex: 0.5, marginTop: 17 }}></div>

          {/* Step 4: Resolved */}
          <div style={{ flex: 1, textAlign: 'center' }}>
            <div style={{
              width: 34, height: 34, borderRadius: '50%',
              background: p.status === 'resolved' ? '#16a34a' : 'var(--card-border, #e2e8f0)',
              color: p.status === 'resolved' ? 'white' : 'var(--muted, #64748b)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 6px', fontWeight: 'bold'
            }}>
              {p.status === 'resolved' ? '✓' : '4'}
            </div>
            <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>Resolved</div>
            <div style={{ fontSize: '0.72rem', color: 'var(--muted, #64748b)' }}>
              {p.status === 'resolved' ? 'Completed' : 'Pending'}
            </div>
          </div>
        </div>
      </div>

      {p.is_duplicate && p.duplicate_of && (
        <div className="note note-warn">
          <IconAlert size={22} />
          <div>
            <b>This looks like a problem that was already reported:</b>{' '}
            <Link to={`/problem/${p.duplicate_of.id}`}>{p.duplicate_of.title}</Link>.
            {user && (
              <div className="fb-buttons" style={{ marginTop: 10 }}>
                <button className="btn btn-outline" onClick={() => sendDuplicateFeedback(true)}>
                  <IconCheck size={18} /> Yes, it is the same
                </button>
                <button className="btn btn-outline" onClick={() => sendDuplicateFeedback(false)}>
                  <IconX size={18} /> No, it is different
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {isAssignedTeam && (
        <div className={`card note ${p.status === 'resolved' ? 'note-success' : 'note-info'}`} style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 14 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: '1.05rem', color: p.status === 'resolved' ? '#16a34a' : 'var(--blue, #2563eb)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <IconCheck size={20} />
                {p.status === 'resolved' ? 'Problem Solved by Your Team' : 'Your Team is Handling This Problem'}
              </div>
              <p style={{ margin: '4px 0 0 0', color: 'var(--muted, #64748b)' }}>
                {p.status === 'resolved'
                  ? 'Great work! This problem has been marked as completed and resolved for the community.'
                  : 'Have you completed the work on this issue? You can mark it as completed/solved now.'}
              </p>
            </div>
            {p.status === 'resolved' ? (
              <button className="btn btn-outline btn-sm" onClick={() => changeStatus('assigned')}>
                Reopen / Mark In Progress
              </button>
            ) : (
              <button
                className="btn btn-primary"
                style={{ background: '#16a34a', borderColor: '#16a34a' }}
                onClick={() => changeStatus('resolved')}
              >
                <IconCheck size={18} /> Mark as Completed
              </button>
            )}
          </div>
        </div>
      )}

      <div className="result-grid">
        <div className="card">
          <h2>What was reported</h2>
          <p>{p.description}</p>
          <div className="card-meta">
            <span className="meta-item"><IconClock size={18} /> {new Date(p.created_at).toLocaleString()}</span>
          </div>
          {p.location && (
            <div className="loc-block">
              <div>
                <div className="loc-label"><IconMapPin size={16} /> Where</div>
                <div className="loc-text">{p.location}</div>
              </div>
              <LocationButton location={p.location} />
            </div>
          )}
          {canChangeStatus && (
            <div className="filter-inline">
              <label className="fl-block">
                <span>Change status</span>
                <Select
                  value={p.status}
                  onChange={changeStatus}
                  options={['open', 'in_review', 'assigned', 'resolved'].map((s) => ({
                    value: s,
                    label: statusLabel(s),
                  }))}
                />
              </label>
            </div>
          )}
        </div>

        <div className="card">
          <h2>Similar reports</h2>
          {p.similar?.length === 0 ? (
            <p className="muted">No similar reports found.</p>
          ) : (
            p.similar.map((s) => (
              <div className="similar-row" key={s.id}>
                <Link to={`/problem/${s.id}`}>{s.title}</Link>
                <span className="muted">{Math.round((s.score ?? 0) * 100)}% alike</span>
              </div>
            ))
          )}
        </div>

        <div className="card">
          {hasAcceptedTeam ? (
            <>
              <h2>Assigned Team</h2>
              <div className={acceptedTeam.status === 'accepted' ? 'note note-ok' : 'note note-info'} style={{ marginBottom: 14 }}>
                <IconCheck size={20} />
                <div>
                  {acceptedTeam.status === 'accepted' ? (
                    <><b>Team Confirmed:</b> <b>{acceptedTeam.team_name}</b> accepted this problem and is actively resolving it.</>
                  ) : (
                    <><b>AI Auto-Assigned:</b> AI automatically assigned this problem to <b>{acceptedTeam.team_name}</b> based on cluster analysis &amp; skills. Awaiting team review.</>
                  )}
                </div>
              </div>
              <div className="rec-block" style={{ borderLeft: `4px solid ${acceptedTeam.status === 'accepted' ? 'var(--ok, #16a34a)' : 'var(--warn, #d97706)'}`, padding: 14 }}>
                <div className="rec-head">
                  <b style={{ fontSize: '1.1rem' }}>{acceptedTeam.team_name}</b>
                  <Badge tone={acceptedTeam.status === 'accepted' ? 'green' : 'amber'}>
                    {acceptedTeam.status === 'accepted' ? 'Accepted & In Progress' : 'AI Assigned (Pending Confirmation)'}
                  </Badge>
                </div>
                {acceptedTeam.explanation && (
                  <div className="muted" style={{ margin: '8px 0' }}>{acceptedTeam.explanation}</div>
                )}
                {acceptedTeam.matched_keywords?.length > 0 && (
                  <div className="kw-row" aria-label="Matching skills and areas" style={{ marginTop: 8 }}>
                    {acceptedTeam.matched_keywords.map((k) => (
                      <span className="kw" key={k}>{k}</span>
                    ))}
                  </div>
                )}
                <div style={{ marginTop: 14 }}>
                  <Link to={`/teams/${acceptedTeam.team_id}`} className="btn btn-outline btn-sm">
                    View Team Details
                  </Link>
                </div>
              </div>
            </>
          ) : (
            <>
              <h2>Teams that may help</h2>
              {p.recommended_teams?.length === 0 ? (
                <p className="muted">No teams suggested yet.</p>
              ) : (
                p.recommended_teams.map((t) => (
                  <div className="rec-block" key={t.match_id}>
                    <div className="rec-head">
                      <b>{t.ranking}. {t.team_name}</b>
                      <Badge tone={t.status === 'accepted' ? 'green' : t.status === 'rejected' ? 'red' : 'gray'}>
                        {t.status === 'accepted' ? 'Accepted' : t.status === 'rejected' ? 'Declined' : 'Suggested'}
                      </Badge>
                    </div>
                    <div className="muted">{t.explanation}</div>
                    {t.matched_keywords?.length > 0 && (
                      <div className="kw-row" aria-label="Matching words">
                        {t.matched_keywords.map((k) => (
                          <span className="kw" key={k}>{k}</span>
                        ))}
                      </div>
                    )}
                    <div className="rec-foot">
                      <span className="muted">Fit: <b>{Math.round((t.score ?? 0) * 100)}%</b></span>
                      {user && (
                        <div className="fb-buttons">
                          <button className="btn btn-outline" onClick={() => sendFeedback(t.match_id, 'good_match')}><IconThumbsUp size={18} /> Good match</button>
                          <button className="btn btn-outline" onClick={() => sendFeedback(t.match_id, 'bad_match')}><IconThumbsDown size={18} /> Not a match</button>
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}

              {user && (
                <div className="form-inline">
                  <input
                    value={feedbackComment}
                    onChange={(e) => setFeedbackComment(e.target.value)}
                    placeholder="Add a note (optional)"
                  />
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {analysis && (
        <div className="card">
          <button className="btn btn-outline" onClick={() => setShowNlp((s) => !s)} aria-expanded={showNlp}>
            {showNlp ? 'Hide technical details' : 'Show technical details (for the curious)'}
          </button>

          {showNlp && (
            <>
            <p className="muted">
              Model: {analysis.embedder === 'sentence'
                ? `sentence-transformers (${analysis.sentence_model})`
                : 'TF-IDF baseline'}
              {' '}· duplicate threshold: {analysis.threshold} · cluster: {p.cluster || 'unassigned'}
            </p>
      <div className="ai-strip">
        <div className="ai-strip-item" title="Trained duplicate classifier">
          <span className="ai-strip-icon" aria-hidden="true"><IconRefresh size={19} /></span>
          <div>
            <div className="ai-strip-value">
              {p.is_duplicate
                ? `Duplicate · ${Math.round((p.duplicate_score ?? 0) * 100)}%`
                : `${Math.round((p.duplicate_score ?? 0) * 100)}% top similarity`}
            </div>
            <div className="ai-strip-label">
              {trainedDup ? 'trained classifier' : 'semantic similarity'}
              {p.is_duplicate && p.duplicate_of ? ` · of #${p.duplicate_of.id}` : ''}
            </div>
          </div>
        </div>
        <div className="ai-strip-item" title="K-Means problem cluster">
          <span className="ai-strip-icon" aria-hidden="true"><IconBox size={19} /></span>
          <div>
            <div className="ai-strip-value">{p.cluster || 'Unassigned'}</div>
            <div className="ai-strip-label">problem cluster</div>
          </div>
        </div>
        {topSimilar && (
          <div className="ai-strip-item" title="Most similar existing report">
            <span className="ai-strip-icon" aria-hidden="true"><IconMagnet size={19} /></span>
            <div>
              <div className="ai-strip-value">
                <Link to={`/problem/${topSimilar.id}`}>#{topSimilar.id} similar</Link>
              </div>
              <div className="ai-strip-label">
                {Math.round((topSimilar.score ?? 0) * 100)}% cosine match
              </div>
            </div>
          </div>
        )}
        {topTeam && !hasAcceptedTeam && (
          <div className="ai-strip-item" title="Top recommended student team">
            <span className="ai-strip-icon" aria-hidden="true"><IconGraduationCap size={19} /></span>
            <div>
              <div className="ai-strip-value">{topTeam.team_name}</div>
              <div className="ai-strip-label">
                #1 team · score {(topTeam.score ?? 0).toFixed(2)}
              </div>
            </div>
          </div>
        )}
        {acceptedTeam && (
          <div className="ai-strip-item" title="Assigned team">
            <span className="ai-strip-icon" aria-hidden="true"><IconGraduationCap size={19} /></span>
            <div>
              <div className="ai-strip-value">{acceptedTeam.team_name}</div>
              <div className="ai-strip-label">
                assigned team
              </div>
            </div>
          </div>
        )}
      </div>

            <div className="nlp-panel">
              <div className="nlp-col">
                <h4>NLP preprocessing</h4>
                <p className="muted small">
                  Lowercasing → markup/punctuation removal → tokenization → stop-word removal →
                  suffix normalization.
                </p>
                <div className="kw-row">
                  {nlp.tokens.map((t, i) => (
                    <span className="kw" key={`${t}-${i}`}>{t}</span>
                  ))}
                </div>
                <p className="muted small">{nlp.token_count} content tokens kept</p>
              </div>

              <div className="nlp-col">
                <h4>Top keywords (TF-IDF weights)</h4>
                <div className="kw-row">
                  {nlp.top_keywords.map(([term, w]) => (
                    <span className="kw kw-weighted" key={term} title={`weight ${w}`}>
                      {term} <i>{w.toFixed(2)}</i>
                    </span>
                  ))}
                </div>
              </div>

              <div className="nlp-col">
                <h4>Team score breakdown</h4>
                {(analysis.matches || []).slice(0, 3).map((m) => (
                  <div className="metric-row" key={m.match_id}>
                    <span>
                      #{m.ranking} {m.team_name}
                      {m.breakdown && (
                        <i className="muted">
                          {' '}· text {m.breakdown.text_similarity?.toFixed(2)} · keywords{' '}
                          {m.breakdown.keyword_coverage?.toFixed(2)}
                          {m.breakdown.model_score != null && (
                            <> · formula {m.breakdown.formula_score?.toFixed(2)}</>
                          )}
                        </i>
                      )}
                    </span>
                    <b>
                      {m.score?.toFixed(2)}
                      {m.scoring_model && <i className="muted"> trained-ranker</i>}
                    </b>
                  </div>
                ))}
                <p className="muted small">
                  {analysis.matches?.some((m) => m.scoring_model)
                    ? 'score = trained ranker probability (scripts/train_ranker.py); the weighted formula score is shown alongside for transparency.'
                    : 'score = 0.60·text similarity + 0.35·keyword coverage + 0.05·experience (sentence embedder weights).'}
                </p>
              </div>
            </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
