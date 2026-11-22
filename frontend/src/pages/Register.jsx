import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth.jsx'
import { Select } from '../components/ui.jsx'
import { IconInbox } from '../components/icons.jsx'

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('citizen')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = await register({ name, email, password, role })
      if (result && result.needsConfirmation) {
        // Real Supabase account created — it activates after the user
        // clicks the confirmation link in their inbox.
        setSent(true)
        return
      }
      // Email confirmation disabled on the project — straight into the app.
      window.location.assign(result.role === 'team' ? '/team' : '/dashboard')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (sent) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <div className="auth-brand">
            <span className="brand-icon"><img src="/logo-mark.png" alt="" aria-hidden="true" /></span>
            <span>Civic<span className="grad">AI</span></span>
          </div>
          <div className="confirm-ico" aria-hidden="true"><IconInbox size={40} /></div>
          <h1>Check your email</h1>
          <p className="muted center">
            We sent a message to <b>{email}</b>. Open it and press the link inside to switch on your account. Then come back and log in.
          </p>
          <Link to="/login" className="btn btn-primary btn-block" style={{ marginTop: 16 }}>
            Go to log in
          </Link>
          <p className="muted center">
            Cannot find it? Look in your spam folder, or wait a minute and try again.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <Link to="/" className="auth-back">← Back to start page</Link>
        <div className="auth-brand">
          <span className="brand-icon"><img src="/logo-mark.png" alt="" aria-hidden="true" /></span>
          <span>Civic<span className="grad">AI</span></span>
        </div>
        <h1>Create your account</h1>
        <p className="muted">It is free and takes about a minute.</p>
        <form onSubmit={submit} className="form">
          <label>Your full name
            <input value={name} onChange={(e) => setName(e.target.value)} required minLength={2} />
          </label>
          <label>Your email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
          </label>
          <label>Choose a password <span className="hint">(at least 6 letters or numbers)</span>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} autoComplete="new-password" />
          </label>
          <label>I want to…
            <Select
              className="auth-select"
              value={role}
              onChange={setRole}
              options={[
                { value: 'citizen', label: 'Report problems in my area' },
                { value: 'team', label: 'Help solve problems (student team)' },
              ]}
            />
          </label>
          {error && <div className="note note-error" role="alert">{error}</div>}
          <button className="btn btn-primary btn-lg btn-block" disabled={busy}>
            {busy ? 'Creating your account…' : 'Create my account'}
          </button>
        </form>
        <p className="muted center">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  )
}
