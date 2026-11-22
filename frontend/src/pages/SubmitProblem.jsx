import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { ErrorNote, LocationButton } from '../components/ui.jsx'
import { IconAlert, IconCheck, IconCheckCircle, IconClock, IconEdit, IconGraduationCap, IconMapPin, IconPlus, IconSearch } from '../components/icons.jsx'

/* What happens after "Send my report" — shown in plain words while we wait. */
const WORKING_STEPS = [
  { icon: IconEdit, label: 'Reading your report' },
  { icon: IconSearch, label: 'Checking if it was reported before' },
  { icon: IconGraduationCap, label: 'Finding a team that can help' },
]

/* Big buttons instead of typing a category. `value` is what the app stores. */
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
    const t = setInterval(() => setStep((s) => Math.min(s + 1, WORKING_STEPS.length - 1)), 700)
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
    return (
      <div className="narrow-wide">
        <div className="page-head">
          <div>
            <h1>Thank you — your report was sent</h1>
            <p className="page-sub">Here is what we found. You can follow this report any time under “My Reports”.</p>
          </div>
        </div>

        {a.duplicate ? (
          <div className="note note-warn">
            <IconAlert size={22} />
            <div>
              <b>Someone may have reported this already.</b> It looks very similar to
              {' '}&ldquo;{a.duplicate.title}&rdquo;.
              Your report is saved and an administrator will look at it.
            </div>
          </div>
        ) : (
          <div className="note note-ok">
            <IconCheckCircle size={22} />
            <div><b>Good news.</b> Nobody has reported this problem before.</div>
          </div>
        )}

        <div className="stack">
          <div className="card">
            <h2>Your report</h2>
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

          {a.similar_problems.length > 0 && (
            <div className="card">
              <h2>Similar reports</h2>
              {a.similar_problems.map((s) => (
                <div className="similar-row" key={s.id}>
                  <Link to={`/problem/${s.id}`}>{s.title}</Link>
                  <span className="muted">{Math.round((s.score ?? 0) * 100)}% alike</span>
                </div>
              ))}
            </div>
          )}

          {a.recommended_teams.length > 0 && (
            <div className="card">
              <h2>Teams that may help</h2>
              {a.recommended_teams.slice(0, 3).map((t, i) => (
                <div className="rec-row" key={t.team_id}>
                  <div>
                    <b>{i + 1}. {t.team_name}</b>
                    <div className="muted">{t.explanation}</div>
                  </div>
                </div>
              ))}
              <p className="muted">These teams will see your report in their list.</p>
            </div>
          )}
        </div>

        <div className="action-row">
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
          <h2>Please wait a moment…</h2>
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
