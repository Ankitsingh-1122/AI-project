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
          <p className="muted" style={{ textAlign: 'center' }}>
            Your CivicAI account was created on Supabase. We sent a confirmation link to
            <b> {email}</b> — click it to activate your account, then log in here.
          </p>
          <Link to="/login" className="btn btn-primary btn-block" style={{ marginTop: 16 }}>
            Back to log in
          </Link>
          <p className="muted center" style={{ fontSize: 12 }}>
            Didn&apos;t get it? Check spam, or wait a minute and try again.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <span className="brand-icon"><img src="/logo-mark.png" alt="" aria-hidden="true" /></span>
          <span>Civic<span className="grad">AI</span></span>
        </div>
        <h1>Create your account</h1>
        <p className="muted">Real accounts on Supabase — citizens report problems · teams solve them</p>
        <form onSubmit={submit}>
          <label>Full name
            <input value={name} onChange={(e) => setName(e.target.value)} required minLength={2} />
          </label>
          <label>Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} />
          </label>
          <label>I am a…
            <Select
              className="auth-select"
              value={role}
              onChange={setRole}
              options={[
                { value: 'citizen', label: 'Citizen (report problems)' },
                { value: 'team', label: 'Student team (solve problems)' },
              ]}
            />
          </label>
          {error && <div className="note note-error">{error}</div>}
          <button className="btn btn-primary btn-block" disabled={busy}>
            {busy ? 'Creating…' : 'Create account'}
          </button>
        </form>
        <p className="muted center">
          Already registered? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  )
}
