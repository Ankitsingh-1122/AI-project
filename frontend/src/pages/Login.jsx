import { useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth.jsx'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [params] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const user = await login(email, password)
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
    } finally {
      setBusy(false)
    }
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
          <b>Demo accounts (seeded data)</b>
          <button type="button" onClick={() => { setEmail('admin@civic.demo'); setPassword('admin123') }}>admin</button>
          <button type="button" onClick={() => { setEmail('citizen1@civic.demo'); setPassword('demo123') }}>citizen</button>
          <button type="button" onClick={() => { setEmail('team1@civic.demo'); setPassword('demo123') }}>team</button>
        </div>
      </div>
    </div>
  )
}
