import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useToast } from '../toast.jsx'
import { Badge, DuplicateBadge, ErrorNote, LocationButton, ScoreBar, Select, Spinner, statusTone } from '../components/ui.jsx'

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
      toast.push(`Feedback recorded: ${type === 'good_match' ? 'good match 👍' : 'bad match 👎'}`)
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
          ? 'Thanks — confirmed the duplicate flag 👍'
          : 'Thanks — flagged the duplicate decision for review'
      )
      setFeedbackComment('')
    } catch (err) {
      if (err.status !== 401) toast.push(`Feedback error: ${err.message}`, 'error')
    }
  }

  async function changeStatus(status) {
    try {
      const data = await api(`/api/problems/${id}`, { method: 'PUT', body: { status } })
      setP(data.problem)
      toast.push(`Status updated to ${status}`)
    } catch (err) {
      if (err.status !== 401) setError(err.message)
    }
  }

  if (error && !p) return <ErrorNote>{error}</ErrorNote>
  if (!p) return <Spinner />

  const canEdit = user && (user.role === 'admin' || user.role === 'citizen')
  const nlp = analysis?.nlp
  const topSimilar = p.similar?.[0]
  const topTeam = p.recommended_teams?.[0]
  const trainedDup = analysis?.duplicate?.method === 'trained_classifier'

  return (
    <div>
      <div className="page-head">
        <div>
          <p className="muted"><Link to="/dashboard">← back to my problems</Link></p>
          <h1>#{p.id} · {p.title}</h1>
        </div>
        <div className="card-badges">
          <Badge tone={statusTone(p.status)}>{p.status.replace(/_/g, ' ')}</Badge>
          <Badge tone="blue">{p.category.replace(/_/g, ' ')}</Badge>
          <DuplicateBadge p={p} />
        </div>
      </div>

      <ErrorNote>{error}</ErrorNote>

      {p.is_duplicate && p.duplicate_of && (
        <div className="note note-warn">
          ⚠️ Flagged as a <b>duplicate</b> of{' '}
          <Link to={`/problem/${p.duplicate_of.id}`}>#{p.duplicate_of.id} · {p.duplicate_of.title}</Link>{' '}
          ({trainedDup
            ? `classifier probability ${(p.duplicate_score ?? 0).toFixed(2)}`
            : `similarity ${(p.duplicate_score ?? 0).toFixed(2)}`}, threshold {analysis?.threshold ?? '—'}).
          {user && (
            <div className="fb-buttons" style={{ marginTop: 8 }}>
              <button className="btn btn-ghost btn-sm" onClick={() => sendDuplicateFeedback(true)}>
                ✓ yes, duplicate
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => sendDuplicateFeedback(false)}>
                ✕ not a duplicate
              </button>
            </div>
          )}
        </div>
      )}

      {/* AI insight strip — every value comes from the live analysis payload */}
      <div className="ai-strip">
        <div className="ai-strip-item" title="Trained duplicate classifier">
          <span className="ai-strip-icon">🔁</span>
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
          <span className="ai-strip-icon">📦</span>
          <div>
            <div className="ai-strip-value">{p.cluster || 'Unassigned'}</div>
            <div className="ai-strip-label">problem cluster</div>
          </div>
        </div>
        {topSimilar && (
          <div className="ai-strip-item" title="Most similar existing report">
            <span className="ai-strip-icon">🧲</span>
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
        {topTeam && (
          <div className="ai-strip-item" title="Top recommended student team">
            <span className="ai-strip-icon">🎓</span>
            <div>
              <div className="ai-strip-value">{topTeam.team_name}</div>
              <div className="ai-strip-label">
                #1 team · score {(topTeam.score ?? 0).toFixed(2)}
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="result-grid">
        <div className="card">
          <h3>Details</h3>
          <p className="card-text">{p.description}</p>
          <div className="card-meta">
            <span>📦 cluster: {p.cluster || '—'}</span>
            <span>🕒 {new Date(p.created_at).toLocaleString()}</span>
          </div>
          {p.location && (
            <div className="loc-block">
              <div>
                <div className="loc-label">📍 Reported location</div>
                <div className="loc-text">{p.location}</div>
              </div>
              <LocationButton location={p.location} />
            </div>
          )}
          {canEdit && (
            <div className="filter-inline">
              <label className="fl-block">
                <span>Status</span>
                <Select
                  value={p.status}
                  onChange={changeStatus}
                  options={['open', 'in_review', 'assigned', 'resolved'].map((s) => ({
                    value: s,
                    label: s.replace(/_/g, ' '),
                  }))}
                />
              </label>
            </div>
          )}
        </div>

        <div className="card">
          <h3>Similar problems (semantic similarity)</h3>
          {p.similar?.length === 0 ? (
            <p className="muted">No similar problems found.</p>
          ) : (
            p.similar.map((s) => (
              <div className="similar-row" key={s.id}>
                <Link to={`/problem/${s.id}`}>#{s.id} {s.title}</Link>
                <ScoreBar value={s.score} label />
              </div>
            ))
          )}
          <p className="muted small">
            Cosine similarity — e.g. &ldquo;street light is broken&rdquo; ≈ &ldquo;the streetlamp has
            stopped working&rdquo;.
          </p>
        </div>

        <div className="card">
          <h3>Recommended student teams</h3>
          {p.recommended_teams?.length === 0 ? (
            <p className="muted">No team recommendations yet.</p>
          ) : (
            p.recommended_teams.map((t) => (
              <div className="rec-block" key={t.match_id}>
                <div className="rec-head">
                  <b>#{t.ranking} {t.team_name}</b>
                  <Badge tone={t.status === 'accepted' ? 'green' : t.status === 'rejected' ? 'red' : 'gray'}>
                    {t.status}
                  </Badge>
                </div>
                <div className="muted small">{t.explanation}</div>
                {t.matched_keywords?.length > 0 && (
                  <div className="kw-row">
                    {t.matched_keywords.map((k) => (
                      <span className="kw" key={k}>{k}</span>
                    ))}
                  </div>
                )}
                <div className="rec-foot">
                  <ScoreBar value={t.score} label />
                  {user && (
                    <div className="fb-buttons">
                      <button className="btn btn-ghost btn-sm" onClick={() => sendFeedback(t.match_id, 'good_match')}>👍</button>
                      <button className="btn btn-ghost btn-sm" onClick={() => sendFeedback(t.match_id, 'bad_match')}>👎</button>
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
                placeholder="Optional comment for your feedback…"
              />
            </div>
          )}
        </div>
      </div>

      {analysis && (
        <div className="card">
          <button className="link-btn" onClick={() => setShowNlp((s) => !s)}>
            {showNlp ? '▾' : '▸'} AI/ML pipeline details
            <span className="muted small">
              {' '}· model: {analysis.embedder === 'sentence'
                ? `sentence-transformers (${analysis.sentence_model})`
                : 'TF-IDF baseline'}
              {' '}· duplicate threshold: {analysis.threshold}
            </span>
          </button>

          {showNlp && (
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
          )}
        </div>
      )}
    </div>
  )
}
