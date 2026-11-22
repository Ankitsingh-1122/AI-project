import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import TextSize from '../components/TextSize.jsx'
import { IconEdit, IconSearch, IconUsers } from '../components/icons.jsx'

/* The real pipeline, step by step (same order the backend runs it). */
const AI_STEPS = [
  {
    title: 'Submit a problem',
    text: 'A citizen writes the title, description, location and (optionally) the kind of problem.',
    tags: ['title', 'description', 'location', 'category'],
    example: 'Street light is not working near the bus stand',
  },
  {
    title: 'Clean up the text (NLP preprocessing)',
    text: 'The computer cannot read a sentence the way we do, so the text is first cleaned and broken into small pieces.',
    tags: ['lowercasing', 'tokenization', 'stop-word removal', 'normalization / stemming'],
    example: <><b>Tokens:</b> street · light · not · working · bus · stand → <b>kept:</b> street · light · work · bus · stand</>,
  },
  {
    title: 'Turn the meaning into numbers (embedding)',
    text: 'A pretrained language model converts the sentence into a list of numbers that captures its meaning, so “street light is broken” and “the streetlamp stopped working” end up close together.',
    tags: ['sentence embeddings', 'all-MiniLM-L6-v2', 'TF-IDF keywords'],
  },
  {
    title: 'Check for duplicates',
    text: 'The new report is compared with every existing report. If it is almost the same as one already reported, it is flagged as a duplicate.',
    tags: ['cosine similarity', 'duplicate classifier', 'tuned threshold'],
  },
  {
    title: 'Group similar problems (clustering)',
    text: 'All reports are grouped into clusters such as lighting, roads or water, so related problems can be handled together.',
    tags: ['K-Means', 'DBSCAN compared', 'silhouette score'],
  },
  {
    title: 'Match with the right student team',
    text: 'Each team’s skills, interests and experience are compared with the problem. Teams are ranked, with a short explanation of why they fit.',
    tags: ['skills', 'interests', 'experience', 'explainable ranking'],
  },
  {
    title: 'Team accepts, you follow progress',
    text: 'The best-fitting teams are notified. A team accepts the problem and the status changes, so the citizen can follow it.',
    tags: ['notifications', 'status updates', 'feedback'],
  },
]


const STEPS = [
  { icon: IconEdit, title: 'Tell us the problem', text: 'Write what is wrong and where. A broken street light, a pothole, a water problem — anything in your area.' },
  { icon: IconSearch, title: 'We check it', text: 'We look to see if someone already reported the same thing, so nothing is counted twice.' },
  { icon: IconUsers, title: 'A team helps', text: 'Your report is sent to a student team with the right skills. You can follow what happens next.' },
]

export default function Landing() {
  const { user } = useAuth()
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
        <div className="topbar-row">
          <Link to="/" className="topbar-brand" aria-label="CivicAI home">
            <span className="brand-icon"><img src="/logo-mark.png" alt="" aria-hidden="true" /></span>
            <span className="brand-text">Civic<span className="grad">AI</span></span>
          </Link>
          <div className="topbar-spacer" />
          <TextSize />
          {user ? (
            <Link to={home} className="btn btn-primary">Go to my page</Link>
          ) : (
            <Link to="/login" className="btn btn-outline">Log in</Link>
          )}
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="hero-text">
            <h1>
              Report a problem in your area. <span className="grad">We will help get it fixed.</span>
            </h1>
            <p className="hero-sub">
              Tell us about a broken street light, a pothole or any other problem near you.
              We connect it with a student team that can help.
            </p>
            <div className="hero-cta">
              {user ? (
                <Link to={home} className="btn btn-primary btn-lg">Go to my page</Link>
              ) : (
                <>
                  <Link to="/register" className="btn btn-primary btn-lg">Create a free account</Link>
                  <Link to="/login" className="btn btn-outline btn-lg">I already have an account</Link>
                </>
              )}
            </div>
          </div>

          <div className="hero-side">
            <img src="/logo.png" className="hero-logo" alt="CivicAI — Smart Citizens, Smart Solutions" />
            {stats && (
              <div className="hero-stats">
                <div className="hstat"><b>{stats.total_problems}</b><span>problems reported</span></div>
                <div className="hstat"><b>{stats.teams}</b><span>student teams ready to help</span></div>
              </div>
            )}
          </div>
        </section>

        <section className="how">
          <h2>How it works</h2>
          <ol className="how-steps">
            {STEPS.map((s, i) => (
              <li className="how-step" key={s.title}>
                <span className="how-num" aria-hidden="true">{i + 1}</span>
                <div className="feature-icon" aria-hidden="true"><s.icon size={26} /></div>
                <h3>{s.title}</h3>
                <p>{s.text}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="ai-flow-section" aria-labelledby="ai-flow-title">
          <h2 id="ai-flow-title">How the AI works, step by step</h2>
          <p className="ai-flow-intro">
            This is what happens behind the scenes from the moment someone submits a problem.
          </p>
          <ol className="ai-flow">
            {AI_STEPS.map((st, i) => (
              <li className="ai-step" key={st.title}>
                <span className="ai-num" aria-hidden="true">{i + 1}</span>
                <div className="ai-card">
                  <h3>{st.title}</h3>
                  <p>{st.text}</p>
                  <div className="ai-tags">
                    {st.tags.map((t) => <span className="ai-tag" key={t}>{t}</span>)}
                  </div>
                  {st.example && <div className="ai-example">{st.example}</div>}
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section className="demo-section">
          <details className="demo-details">
            <summary>Just want to look around? Use a demo login</summary>
            <p className="muted">These sample accounts have example data. On the Log in page you can also press one button to sign in.</p>
            <ul className="demo-list">
              <li><b>Citizen:</b> citizen1@civic.demo / demo123</li>
              <li><b>Student team:</b> team1@civic.demo / demo123</li>
              <li><b>Administrator:</b> admin@civic.demo / admin123</li>
            </ul>
          </details>
        </section>
      </main>

      <footer className="footer">
        CivicAI · Report a problem in your area and we connect it with a team that can help.
      </footer>
    </div>
  )
}
