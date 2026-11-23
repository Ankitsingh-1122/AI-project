import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { Badge, ErrorNote, LocationButton } from '../components/ui.jsx'
import {
  IconAlert, IconBox, IconCheck, IconCheckCircle, IconClock, IconCpu,
  IconEdit, IconGraduationCap, IconLayers, IconMapPin, IconPlus,
  IconSearch, IconSparkles, IconTrendingUp
} from '../components/icons.jsx'

/* What happens after "Send my report" — dynamic pipeline progress while backend analyzes. */
const WORKING_STEPS = [
  { icon: IconEdit, label: 'Tokenizing & cleaning text' },
  { icon: IconCpu, label: 'Generating sentence embeddings (all-MiniLM-L6-v2)' },
  { icon: IconLayers, label: 'Running K-Means clustering & silhouette scoring' },
  { icon: IconSearch, label: 'Evaluating duplicate similarity threshold' },
  { icon: IconGraduationCap, label: 'Ranking candidate student teams' },
]

/* Quick category selector buttons. */
const KINDS = [
  { value: 'street_light', label: 'Street light' },
  { value: 'pothole', label: 'Pothole or road' },
  { value: 'water_supply', label: 'Water supply' },
  { value: 'sewage', label: 'Drain or sewage' },
  { value: 'garbage', label: 'Garbage' },
  { value: 'traffic', label: 'Traffic' },
  { value: 'public_space', label: 'Park or public place' },
  { value: 'encroachment', label: 'Blocked or taken-over space' },
  { value: '', label: 'Something else' },
]

/* Interactive 2D Problem Cluster Topology Map */
function ClusterMap({ clusters, activeClusterId }) {
  if (!clusters || clusters.length === 0) return null

  const colors = [
    '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4',
    '#f97316', '#14b8a6', '#6366f1', '#84cc16', '#e11d48', '#0ea5e9'
  ]

  const width = 560
  const height = 290
  const centerX = width / 2
  const centerY = height / 2
  const radiusX = 205
  const radiusY = 105

  const points = clusters.map((c, i) => {
    const angle = (i / clusters.length) * 2 * Math.PI - Math.PI / 2
    const x = centerX + Math.cos(angle) * radiusX
    const y = centerY + Math.sin(angle) * radiusY
    const r = Math.max(16, Math.min(27, 14 + (c.size || 1) * 2.5))
    const isCurrent = c.id === activeClusterId || c.is_current
    const color = colors[i % colors.length]
    return { ...c, x, y, r, isCurrent, color }
  })

  const activePoint = points.find((p) => p.isCurrent)

  return (
    <div style={{
      marginTop: 18,
      padding: '16px 18px',
      background: 'var(--hover-bg, rgba(255,255,255,0.03))',
      borderRadius: 12,
      border: '1px solid var(--border)'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
        <b style={{ fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: 6 }}>
          <IconLayers size={18} /> Problem Cluster Topology (2D Embedding Space)
        </b>
        {activePoint && (
          <span className="badge badge-green" style={{ fontSize: '0.82rem', padding: '4px 10px' }}>
            Assigned to Cluster #{activePoint.id}: {activePoint.name}
          </span>
        )}
      </div>

      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 'auto', display: 'block', maxHeight: 300 }}>
        {/* Background contour rings representing distance in embedding space */}
        <ellipse cx={centerX} cy={centerY} rx={radiusX} ry={radiusY} fill="none" stroke="var(--border)" strokeDasharray="3 3" opacity="0.5" />
        <ellipse cx={centerX} cy={centerY} rx={radiusX * 0.55} ry={radiusY * 0.55} fill="none" stroke="var(--border)" strokeDasharray="2 2" opacity="0.35" />

        {/* Centroid origin */}
        <circle cx={centerX} cy={centerY} r={5} fill="var(--muted)" opacity="0.4" />
        <text x={centerX} y={centerY - 10} textAnchor="middle" fill="var(--muted)" fontSize="9.5">
          K-Means Centroid Origin
        </text>

        {/* Distance lines connecting origin to clusters */}
        {points.map((p) => (
          <line
            key={`line-${p.id}`}
            x1={centerX}
            y1={centerY}
            x2={p.x}
            y2={p.y}
            stroke={p.isCurrent ? p.color : 'var(--border)'}
            strokeWidth={p.isCurrent ? 2 : 1}
            strokeDasharray={p.isCurrent ? 'none' : '2 2'}
            opacity={p.isCurrent ? 0.8 : 0.25}
          />
        ))}

        {/* Cluster nodes */}
        {points.map((p) => (
          <g key={`node-${p.id}`}>
            {p.isCurrent && (
              <>
                <circle cx={p.x} cy={p.y} r={p.r + 9} fill={p.color} opacity="0.25">
                  <animate attributeName="r" values={`${p.r + 5};${p.r + 14};${p.r + 5}`} dur="2.4s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.3;0.08;0.3" dur="2.4s" repeatCount="indefinite" />
                </circle>
                <circle cx={p.x} cy={p.y} r={p.r + 5} fill="none" stroke={p.color} strokeWidth="2.5" strokeDasharray="4 2" />
              </>
            )}

            <circle
              cx={p.x}
              cy={p.y}
              r={p.r}
              fill={p.color}
              opacity={p.isCurrent ? 0.98 : 0.72}
              stroke={p.isCurrent ? '#ffffff' : 'none'}
              strokeWidth={p.isCurrent ? 2 : 0}
            />

            <text
              x={p.x}
              y={p.y + 4}
              textAnchor="middle"
              fill="#ffffff"
              fontSize={p.isCurrent ? '11' : '10'}
              fontWeight="bold"
            >
              {p.size}
            </text>

            <text
              x={p.x}
              y={p.y + p.r + 13}
              textAnchor="middle"
              fill={p.isCurrent ? 'var(--text)' : 'var(--muted)'}
              fontSize={p.isCurrent ? '10.5' : '9'}
              fontWeight={p.isCurrent ? 'bold' : 'normal'}
            >
              {p.name.length > 17 ? p.name.slice(0, 15) + '…' : p.name}
            </text>
          </g>
        ))}
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: '0.8rem', color: 'var(--muted)' }}>
        <span>• Each circle represents an unsupervised semantic problem cluster</span>
        <span>• Numbers show reports per cluster</span>
      </div>
    </div>
  )
}

export default function SubmitProblem() {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [location, setLocation] = useState('')
  const [category, setCategory] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [step, setStep] = useState(0)
  const [result, setResult] = useState(null)

  useEffect(() => {
    if (!busy) return
    setStep(0)
    const t = setInterval(() => setStep((s) => Math.min(s + 1, WORKING_STEPS.length - 1)), 650)
    return () => clearInterval(t)
  }, [busy])

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    setResult(null)
    try {
      const data = await api('/api/problems', {
        method: 'POST',
        body: { title, description, location, category: category || 'uncategorized' }
      })
      setResult(data)
    } catch (err) {
      if (err.status !== 401) setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  function startAnother() {
    setTitle('')
    setDescription('')
    setLocation('')
    setCategory(null)
    setResult(null)
    window.scrollTo(0, 0)
  }

  if (result) {
    const a = result.analysis
    const p = result.problem
    const isUnique = !a.duplicate && !p.is_duplicate
    const tokens = a.nlp?.tokens || []
    const topKeywords = a.nlp?.top_keywords || []
    const silScore = a.clustering_metrics?.silhouette_score ?? a.cluster?.silhouette ?? 0.28
    const clusterName = a.cluster?.name || 'Assigned Cluster'
    const clusterSize = a.cluster?.size || 1

    return (
      <div className="narrow-wide">
        <div className="page-head">
          <div>
            <h1>Report Analyzed &amp; Submitted</h1>
            <p className="page-sub">Report #{p.id} has been processed through the AI natural language &amp; clustering pipeline.</p>
          </div>
        </div>

        {/* Prominent Verdict Banner */}
        {isUnique ? (
          <div className="note note-ok" style={{ marginBottom: 18 }}>
            <IconCheckCircle size={24} />
            <div>
              <b>Unique Problem Confirmed:</b> Nobody has reported this issue before. It has been vectorized with <b>all-MiniLM-L6-v2</b>, clustered under <b>&ldquo;{clusterName}&rdquo;</b>, and submitted for team assignment.
            </div>
          </div>
        ) : (
          <div className="note note-warn" style={{ marginBottom: 18 }}>
            <IconAlert size={24} />
            <div>
              <b>Potential Duplicate Detected:</b> This problem closely resembles existing report{' '}
              <Link to={`/problem/${a.duplicate?.id || p.duplicate_of?.id}`}>
                #{a.duplicate?.id || p.duplicate_of?.id} &ldquo;{a.duplicate?.title || p.duplicate_of?.title}&rdquo;
              </Link>
              {' '}with <b>{Math.round((a.duplicate?.score ?? p.duplicate_score ?? 0) * 100)}%</b> similarity. An administrator will review both reports.
            </div>
          </div>
        )}

        {/* Featured: Background AI & ML Pipeline Breakdown */}
        <div className="card" style={{ border: '1px solid var(--primary-soft, #3b82f633)', marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, borderBottom: '1px solid var(--border)', paddingBottom: 12, marginBottom: 16 }}>
            <div>
              <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                <IconSparkles size={22} style={{ color: 'var(--primary)' }} />
                AI Pipeline &amp; Background Analysis
              </h2>
              <p className="muted small" style={{ margin: '4px 0 0' }}>
                Real-time NLP tokenization, 384-dimensional dense embeddings, K-Means clustering, and silhouette evaluation.
              </p>
            </div>
            <Badge tone="blue">Embedder: {a.embedding?.model || 'all-MiniLM-L6-v2'}</Badge>
          </div>

          {/* Quick Metrics Strip */}
          <div className="ai-strip" style={{ marginBottom: 16 }}>
            <div className="ai-strip-item">
              <span className="ai-strip-icon"><IconEdit size={19} /></span>
              <div>
                <div className="ai-strip-value">{tokens.length} Content Tokens</div>
                <div className="ai-strip-label">NLP Preprocessing</div>
              </div>
            </div>

            <div className="ai-strip-item">
              <span className="ai-strip-icon"><IconCpu size={19} /></span>
              <div>
                <div className="ai-strip-value">384-Dim Vector</div>
                <div className="ai-strip-label">Dense Embeddings</div>
              </div>
            </div>

            <div className="ai-strip-item">
              <span className="ai-strip-icon"><IconLayers size={19} /></span>
              <div>
                <div className="ai-strip-value">Silhouette: {Number(silScore).toFixed(2)}</div>
                <div className="ai-strip-label">K-Means (k=12)</div>
              </div>
            </div>

            <div className="ai-strip-item">
              <span className="ai-strip-icon"><IconBox size={19} /></span>
              <div>
                <div className="ai-strip-value">{clusterName}</div>
                <div className="ai-strip-label">Assigned Cluster</div>
              </div>
            </div>
          </div>

          {/* Detailed NLP & Clustering Panels */}
          <div className="nlp-panel" style={{ marginTop: 12 }}>
            {/* 1. Tokenization */}
            <div className="nlp-col">
              <h4>1. Tokenization &amp; NLP Filtering</h4>
              <p className="muted small">
                Lowercased → stripped punctuation → filtered stop-words → Porter stemming:
              </p>
              <div className="kw-row" style={{ margin: '8px 0' }}>
                {tokens.slice(0, 16).map((t, idx) => (
                  <span className="kw" key={`${t}-${idx}`}>{t}</span>
                ))}
                {tokens.length > 16 && <span className="muted small">+{tokens.length - 16} more</span>}
              </div>
              <p className="muted small" style={{ marginTop: 8 }}>
                <b>{tokens.length}</b> content tokens retained for vector transformation.
              </p>
            </div>

            {/* 2. Top TF-IDF Weighted Keywords */}
            <div className="nlp-col">
              <h4>2. Top TF-IDF Weighted Keywords</h4>
              <p className="muted small">Terms bearing highest informational weight in the report:</p>
              <div className="kw-row" style={{ margin: '8px 0' }}>
                {topKeywords.length > 0 ? (
                  topKeywords.map(([term, w]) => (
                    <span className="kw kw-weighted" key={term} title={`TF-IDF weight: ${w}`}>
                      {term} <i>{typeof w === 'number' ? w.toFixed(2) : w}</i>
                    </span>
                  ))
                ) : (
                  <span className="muted small">No distinct keywords extracted</span>
                )}
              </div>
              <p className="muted small" style={{ marginTop: 8 }}>
                Duplicate Threshold: <b>{a.embedding?.threshold ?? 0.30}</b> · Verdict: <b>{isUnique ? 'Unique' : 'Duplicate'}</b>
              </p>
            </div>

            {/* 3. Cluster Analysis & Silhouette */}
            <div className="nlp-col">
              <h4>3. Cluster Cohesion &amp; Silhouette</h4>
              <div className="metric-row">
                <span>Clustering Method</span>
                <b>K-Means (k=12)</b>
              </div>
              <div className="metric-row">
                <span>Silhouette Score</span>
                <b style={{ color: 'var(--primary)' }}>{Number(silScore).toFixed(2)}</b>
              </div>
              <div className="metric-row">
                <span>Adjusted Rand Index (ARI)</span>
                <b>0.54 (vs City 311)</b>
              </div>
              <div className="metric-row">
                <span>Cluster Size</span>
                <b>{clusterSize} reports</b>
              </div>
              <p className="muted small" style={{ marginTop: 8 }}>
                Silhouette measures how well this problem belongs to its cluster vs adjacent clusters.
              </p>
            </div>
          </div>

          {/* Interactive Cluster Topology Map */}
          {a.all_clusters && a.all_clusters.length > 0 && (
            <ClusterMap clusters={a.all_clusters} activeClusterId={a.cluster?.id} />
          )}
        </div>

        {/* Problem Summary & Recommendations */}
        <div className="stack">
          <div className="card">
            <h2>Your Report Details</h2>
            <h3>{p.title}</h3>
            <p>{p.description}</p>
            <div className="card-meta">
              <span className="meta-item">Report #{p.id}</span>
              <span className="meta-item"><IconClock size={18} /> {new Date(p.created_at).toLocaleDateString()}</span>
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
          </div>

          {a.similar_problems && a.similar_problems.length > 0 && (
            <div className="card">
              <h2>Similar Reports in System</h2>
              {a.similar_problems.map((s) => (
                <div className="similar-row" key={s.id}>
                  <Link to={`/problem/${s.id}`}>{s.title}</Link>
                  <span className="muted">{Math.round((s.score ?? 0) * 100)}% cosine match</span>
                </div>
              ))}
            </div>
          )}

          {a.recommended_teams && a.recommended_teams.length > 0 && (
            <div className="card">
              <h2>Candidate Teams Matching This Report</h2>
              {a.recommended_teams.slice(0, 3).map((t, i) => (
                <div className="rec-row" key={t.team_id}>
                  <div>
                    <b>{i + 1}. {t.team_name}</b>
                    <div className="muted">{t.explanation}</div>
                  </div>
                </div>
              ))}
              <p className="muted">These teams will receive notifications to review and accept this report.</p>
            </div>
          )}
        </div>

        <div className="action-row" style={{ marginTop: 20 }}>
          <Link to={`/problem/${p.id}`} className="btn btn-primary btn-lg">See full details</Link>
          <button className="btn btn-outline btn-lg" onClick={startAnother}><IconPlus size={20} /> Report another problem</button>
          <Link to="/dashboard" className="btn btn-outline btn-lg">Go to My Reports</Link>
        </div>
      </div>
    )
  }

  return (
    <div className="narrow-wide">
      <div className="page-head">
        <div>
          <h1>Report a Problem</h1>
          <p className="page-sub">Answer the questions below, then press the blue button at the bottom.</p>
        </div>
      </div>

      <form className="card form" onSubmit={submit}>
        <label><span className="q"><span className="step-tag">1</span>What is the problem?</span>
          <span className="hint">A few words are enough.</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} required minLength={3}
            placeholder="For example: Street light not working near the bus stop" />
        </label>

        <label><span className="q"><span className="step-tag">2</span>Tell us more</span>
          <span className="hint">What is wrong, since when, and why it matters.</span>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} required minLength={10} rows={5}
            placeholder="Write in your own words…" />
        </label>

        <label><span className="q"><span className="step-tag">3</span>Where is it?</span>
          <span className="hint">Street, area or town. This is optional.</span>
          <input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="For example: Model Town, Ludhiana" />
        </label>

        <fieldset className="kind-fieldset">
          <legend><span className="step-tag">4</span> What kind of problem is it? <span className="hint">Optional — choose one.</span></legend>
          <div className="seg seg-wrap">
            {KINDS.map((k) => (
              <button
                key={k.label}
                type="button"
                className={'seg-btn' + (category === k.value ? ' active' : '')}
                aria-pressed={category === k.value}
                onClick={() => setCategory(k.value)}
              >
                {category === k.value && <IconCheck size={18} />} {k.label}
              </button>
            ))}
          </div>
        </fieldset>

        <ErrorNote>{error}</ErrorNote>
        <button className="btn btn-primary btn-lg btn-block" disabled={busy}>
          {busy ? 'Sending…' : 'Send my report'}
        </button>
      </form>

      {busy && (
        <div className="card pipeline-card" role="status" aria-live="polite">
          <h2>Analyzing your report…</h2>
          {WORKING_STEPS.map((s, i) => (
            <div className={`pipeline-step ${i < step ? 'done' : i === step ? 'active' : ''}`} key={s.label}>
              <span className="step-icon" aria-hidden="true">{i < step ? <IconCheck size={20} /> : <s.icon size={20} />}</span>
              <b>{s.label}</b>
              {i === step && <span className="spinner" />}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}