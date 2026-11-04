import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useTheme } from '../theme.jsx'

const FEATURES = [
  { icon: '🔁', title: 'Duplicate detection', text: 'New reports are compared against every existing problem with semantic similarity. Near-duplicates are flagged instantly on submission.' },
  { icon: '🧠', title: 'Semantic understanding', text: '“Street light is broken” and “the streetlamp has stopped working” are recognised as the same problem, even with different words.' },
  { icon: '📦', title: 'Automatic clustering', text: 'Related problems are grouped into meaningful clusters with K-Means, auto-selecting the number of clusters via silhouette score.' },
  { icon: '🎓', title: 'Student-team matching', text: 'Each problem is matched to student teams by skills, interests and experience - with explainable, ranked recommendations.' },
  { icon: '📊', title: 'Measurable AI', text: 'Precision, recall, F1, confusion matrix, Precision@K and cluster purity are computed on labelled evaluation data.' },
  { icon: '👥', title: 'Feedback loop', text: 'Citizens and admins can rate AI decisions; feedback is stored for continuous model improvement.' },
]

export default function Landing() {
  const { user } = useAuth()
  const { theme, toggle } = useTheme()
  const [stats, setStats] = useState(null)

  useEffect(() => {
    api('/api/stats/summary').then(setStats).catch(() => {})
  }, [])

  const home = user
    ? user.role === 'admin' ? '/admin' : user.role === 'team' ? '/team' : '/dashboard'
    : '/'

  return (
    <div className="landing">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-icon"><img src="/logo-mark.png" alt="" aria-hidden="true" /></span> CivicAI
        </Link>
        <div className="topbar-right">
          <button className="theme-btn" onClick={toggle} aria-label="Toggle light / dark mode" title="Toggle light / dark mode">
            <span className={theme === 'dark' ? 'theme-icon sun' : 'theme-icon moon'}>
              {theme === 'dark' ? '☀️' : '🌙'}
            </span>
          </button>
          <Link to={user ? home : '/login'} className="btn btn-ghost btn-sm">
            {user ? 'Open dashboard' : 'Log in'}
          </Link>
          {!user && (
            <Link to="/register" className="btn btn-primary btn-sm">
              Sign up
            </Link>
          )}
        </div>
      </header>

      <section className="hero">
        <div className="hero-text">
          <img src="/logo.png" className="hero-logo" alt="CivicAI — Smart Citizens, Smart Solutions" />
          <span className="hero-badge">🧠 AI/ML civic platform · live trained models</span>
          <h1>
            Citizen problems, <span className="grad">understood</span>, deduplicated & matched.
          </h1>
          <p className="hero-sub">
            An AI/ML platform that detects duplicate civic complaints, clusters related problems,
            and recommends the right student teams to tackle them - with full explainability.
          </p>
          <div className="hero-cta">
            <Link to={user ? home : '/register'} className="btn btn-primary btn-lg">
              {user ? 'Go to dashboard' : 'Get started free'}
            </Link>
            <Link to="/login" className="btn btn-outline btn-lg">
              I have an account
            </Link>
          </div>
          <div className="hero-demo">
            <strong>Demo logins</strong>
            <span>admin@civic.demo / admin123</span>
            <span>citizen1@civic.demo / demo123</span>
            <span>team1@civic.demo / demo123</span>
          </div>
        </div>
        <div className="hero-stats">
          {stats ? (
            <>
              <div className="hstat"><b>{stats.total_problems}</b><span>problems reported</span></div>
              <div className="hstat"><b>{stats.duplicates_detected}</b><span>duplicates caught</span></div>
              <div className="hstat"><b>{stats.clusters}</b><span>clusters formed</span></div>
              <div className="hstat"><b>{stats.teams}</b><span>student teams</span></div>
              <div className="hstat"><b>{stats.recommendations}</b><span>AI recommendations</span></div>
            </>
          ) : (
            <div className="hstat"><b>…</b><span>loading live stats</span></div>
          )}
        </div>
      </section>

      <section className="features">
        {FEATURES.map((f) => (
          <div className="feature-card" key={f.title}>
            <div className="feature-icon">{f.icon}</div>
            <h3>{f.title}</h3>
            <p>{f.text}</p>
          </div>
        ))}
      </section>

      <section className="how">
        <h2>How it works</h2>
        <ol className="steps">
          <li><b>Submit</b> a problem (title, description, location, category).</li>
          <li><b>Preprocess</b> text with NLP: tokenization, stop-words, normalization.</li>
          <li><b>Embed</b> the problem and find the most similar existing reports.</li>
          <li><b>Deduplicate</b> against a threshold tuned experimentally on labelled data.</li>
          <li><b>Cluster</b> all problems with K-Means (auto k via silhouette score).</li>
          <li><b>Match & rank</b> student teams by skills, interests and experience - with explanations.</li>
        </ol>
      </section>

      <footer className="footer">
        CivicAI · React + FastAPI + PostgreSQL/SQLite + scikit-learn + sentence-transformers
      </footer>
    </div>
  )
}
