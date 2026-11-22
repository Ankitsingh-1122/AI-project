import { useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth.jsx'
import { IconShield, IconUser, IconUsers } from '../components/icons.jsx'

const DEMO_ACCOUNTS = [
  { role: 'admin', label: 'Administrator', email: 'admin@civic.demo', password: 'admin123', Icon: IconShield },
  { role: 'citizen', label: 'Citizen', email: 'citizen1@civic.demo', password: 'demo123', Icon: IconUser },
  { role: 'team', label: 'Student team', email: 'team1@civic.demo', password: 'demo123', Icon: IconUsers },
]

export default function Login() {
  const { login } = useAuth()
  const location = useLocation()
  const [params] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [showPw, setShowPw] = useState(false)

  async function doLogin(loginEmail, loginPassword) {
    setBusy(true)
    setError('')
    try {
      const user = await login(loginEmail, loginPassword)
      const next = params.get('next')
      const to =
        next && next !== '/login' ? next :
        location.state?.from?.pathname ||
        (user.role === 'admin' ? '/admin' : user.role === 'team' ? '/team' : '/dashboard')
      // Hard navigation: guarantees a clean session start (cookie + fresh
      // /me) and avoids any stale client-side state after login.
      window.location.assign(to)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  function submit(e) {
    e.preventDefault()
    doLogin(email, password)
  }

  function demoClick(acc) {
    setEmail(acc.email)
    setPassword(acc.password)
    doLogin(acc.email, acc.password)
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <Link to="/" className="auth-back">← Back to start page</Link>
        <div className="auth-brand">
          <span className="brand-icon"><img src="/logo-mark.png" alt="" aria-hidden="true" /></span>
          <span>Civic<span className="grad">AI</span></span>
        </div>
        <h1>Log in</h1>
        <p className="muted">Type your email and password.</p>
        <form onSubmit={submit} className="form">
          <label>Your email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
              autoComplete="email" placeholder="name@example.com" />
          </label>
          <label>Your password
            <span className="pw-wrap">
              <input type={showPw ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} required
                autoComplete="current-password" placeholder="Your password" />
              <button type="button" className="pw-toggle" onClick={() => setShowPw((v) => !v)} aria-pressed={showPw}>
                {showPw ? 'Hide' : 'Show'}
              </button>
            </span>
          </label>
          {error && <div className="note note-error" role="alert">{error}</div>}
          <button className="btn btn-primary btn-lg btn-block" disabled={busy}>
            {busy ? 'Logging in…' : 'Log in'}
          </button>
        </form>
        <p className="auth-alt">
          New here? <Link to="/register">Create an account</Link>
        </p>
        <div className="demo-creds">
          <div className="demo-creds-label">
            Just looking around? <small>Press a button to try a sample account</small>
          </div>
          <div className="demo-btns">
            {DEMO_ACCOUNTS.map(({ role, label, Icon }) => (
              <button key={role} type="button" className={`demo-btn tone-${role}`}
                      disabled={busy} onClick={() => demoClick(DEMO_ACCOUNTS.find(a => a.role === role))}>
                <Icon size={20} aria-hidden="true" />
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
