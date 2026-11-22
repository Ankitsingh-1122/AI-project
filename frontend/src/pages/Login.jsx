import { useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth.jsx'
import { IconShield, IconUser, IconUsers } from '../components/icons.jsx'

const DEMO_ACCOUNTS = [
  { role: 'admin', label: 'Admin', email: 'admin@civic.demo', password: 'admin123', Icon: IconShield },
  { role: 'citizen', label: 'Citizen', email: 'citizen1@civic.demo', password: 'demo123', Icon: IconUser },
  { role: 'team', label: 'Team', email: 'team1@civic.demo', password: 'demo123', Icon: IconUsers },
]

export default function Login() {
  const { login } = useAuth()
  const location = useLocation()
  const [params] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

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
        <div className="auth-brand">
          <span className="brand-icon"><img src="/logo-mark.png" alt="" aria-hidden="true" /></span>
          <span>Civic<span className="grad">AI</span></span>
        </div>
        <h1>Welcome back</h1>
        <p className="muted">Log in to continue to CivicAI</p>
        <form onSubmit={submit}>
          <label>Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="you@example.com" />
          </label>
          <label>Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required placeholder="••••••••" />
          </label>
          {error && <div className="note note-error">{error}</div>}
          <button className="btn btn-primary btn-block" disabled={busy}>
            {busy ? 'Logging in…' : 'Log in'}
          </button>
        </form>
        <p className="muted center">
          No account? <Link to="/register">Create one</Link>
        </p>
        <div className="demo-creds">
          <div className="demo-creds-label">
            Demo accounts <small>seeded data · click to log in</small>
          </div>
          <div className="demo-btns">
            {DEMO_ACCOUNTS.map(({ role, label, Icon }) => (
              <button key={role} type="button" className={`demo-btn tone-${role}`}
                      disabled={busy} onClick={() => demoClick(DEMO_ACCOUNTS.find(a => a.role === role))}>
                <Icon size={15} aria-hidden="true" />
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
