import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { ErrorNote, LocationButton, ScoreBar } from '../components/ui.jsx'
import { IconAlert, IconBack, IconBox, IconCheck, IconCheckCircle, IconClock, IconCpu, IconEdit, IconFileText, IconGraduationCap, IconLayers, IconMapPin, IconRefresh } from '../components/icons.jsx'

const PIPELINE_STEPS = [
  { icon: IconEdit, label: 'NLP preprocessing', detail: 'tokenize · stop-words · normalize' },
  { icon: IconCpu, label: 'Semantic embedding', detail: 'sentence-transformers 384-d vector' },
  { icon: IconRefresh, label: 'Duplicate detection', detail: 'cosine vs all reports, tuned threshold' },
  { icon: IconLayers, label: 'Clustering', detail: 'K-Means with auto k (silhouette)' },
  { icon: IconGraduationCap, label: 'Team matching', detail: 'skills + interests + experience' }
]

export default function SubmitProblem() {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [location, setLocation] = useState('')
  const [category, setCategory] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [step, setStep] = useState(0)
  const [result, setResult] = useState(null)

  useEffect(() => {
    if (!busy) return
    setStep(0)
    const t = setInterval(() => setStep((s) => Math.min(s + 1, PIPELINE_STEPS.length - 1)), 450)
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

  if (result) {
    const a = result.analysis
    const p = result.problem
    return (
      <div>
        <div className="page-head">
          <h1>Problem submitted</h1>
          <Link to="/dashboard" className="btn btn-ghost"><IconBack size={14} /> Back to my problems</Link>
        </div>

        {a.duplicate ? (
          <div className="note note-warn">
            <IconAlert size={16} /> <b>Looks like a duplicate.</b> Very similar to
            {' '}&ldquo;{a.duplicate.title}&rdquo;
            (similarity {(a.duplicate.score ?? 0).toFixed(2)}). It is stored and an admin can review it.
          </div>
        ) : (
          <div className="note note-ok">
            <IconCheckCircle size={16} /> No duplicate found — stored as a <b>unique</b> problem.
          </div>
        )}

        <div className="result-grid">
          <div className="card">
            <h3>Your problem #{p.id}</h3>
            <p className="card-text">{p.description}</p>
            <div className="card-meta">
              <span className="meta-item"><IconFileText size={14} /> {p.category}</span>
              <span className="meta-item"><IconClock size={14} /> {new Date(p.created_at).toLocaleDateString()}</span>
            </div>
            {p.location && (
              <div className="loc-block">
                <div>
                  <div className="loc-label"><IconMapPin size={14} /> Reported location</div>
                  <div className="loc-text">{p.location}</div>
                </div>
                <LocationButton location={p.location} />
              </div>
            )}
            {p.cluster && <div className="note note-info"><IconBox size={15} /> Clustered into <b>{p.cluster}</b></div>}
            <Link to={`/problem/${p.id}`} className="btn btn-primary btn-sm">
              View full AI analysis
            </Link>
          </div>

          <div className="card">
            <h3>Most similar existing problems</h3>
            {a.similar_problems.length === 0 ? (
              <p className="muted">No similar problems found.</p>
            ) : (
              a.similar_problems.map((s) => (
                <div className="similar-row" key={s.id}>
                  <Link to={`/problem/${s.id}`}>
                    #{s.id} {s.title}
                  </Link>
                  <ScoreBar value={s.score} />
                </div>
              ))
            )}
            <p className="muted small">Cosine similarity of semantic embeddings — different words, same meaning still scores high.</p>
          </div>

          <div className="card">
            <h3>Recommended student teams</h3>
            {a.recommended_teams.slice(0, 3).map((t, i) => (
              <div className="rec-row" key={t.team_id}>
                <div>
                  <b>#{i + 1} {t.team_name}</b>
                  <div className="muted small">{t.explanation}</div>
                </div>
                <ScoreBar value={t.score} />
              </div>
            ))}
            <p className="muted small">Ranked by skill overlap + semantic match + experience. Teams get notified in their dashboard.</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="narrow">
      <div className="page-head">
        <h1>Submit a problem</h1>
      </div>
      <form className="card form" onSubmit={submit}>
        <label>Problem title
          <input value={title} onChange={(e) => setTitle(e.target.value)} required minLength={3}
            placeholder="e.g. Street light not working near bus stand" />
        </label>
        <label>Description
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} required minLength={10} rows={5}
            placeholder="Describe the problem in detail — what is wrong, where exactly, since when, why it matters." />
        </label>
        <div className="form-grid">
          <label>Location
            <input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="e.g. Model Town, Ludhiana" />
          </label>
          <label>Category (optional)
            <input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="street_light, pothole…" list="cat-list" />
            <datalist id="cat-list">
              {['street_light', 'pothole', 'water_supply', 'sewage', 'garbage', 'traffic', 'public_space', 'encroachment'].map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>
          </label>
        </div>
        <ErrorNote>{error}</ErrorNote>
        <button className="btn btn-primary btn-block" disabled={busy}>
          {busy ? 'Analyzing…' : 'Submit & analyze'}
        </button>
        <p className="muted small center">
          On submit, the AI runs the full pipeline: NLP preprocessing → semantic embedding →
          duplicate check → K-Means clustering → student-team ranking.
        </p>
      </form>

      {busy && (
        <div className="card pipeline-card">
          <h3>AI pipeline running…</h3>
          {PIPELINE_STEPS.map((s, i) => (
            <div className={`pipeline-step ${i < step ? 'done' : i === step ? 'active' : ''}`} key={s.label}>
              <span className="step-icon" aria-hidden="true">{i < step ? <IconCheck size={16} /> : <s.icon size={16} />}</span>
              <div>
                <b>{s.label}</b>
                <div className="muted small">{s.detail}</div>
              </div>
              {i === step && <span className="spinner" />}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
