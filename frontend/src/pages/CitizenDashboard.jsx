import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api.js'
import { Badge, DuplicateBadge, Empty, Select, statusTone } from '../components/ui.jsx'

export default function CitizenDashboard() {
  const [problems, setProblems] = useState(null)
  const [error, setError] = useState('')
  const [q, setQ] = useState('')
  const [cat, setCat] = useState('all')
  const [status, setStatus] = useState('all')
  const [searchParams, setSearchParams] = useSearchParams()

  // ?dup=unique / ?dup=duplicates deep links (used by the admin dashboard
  // stat cards) — kept in the URL so the view is shareable/bookmarkable.
  const dup = ['unique', 'duplicates'].includes(searchParams.get('dup'))
    ? searchParams.get('dup')
    : 'all'

  function setDup(v) {
    const p = new URLSearchParams(searchParams)
    if (v === 'all') p.delete('dup')
    else p.set('dup', v)
    setSearchParams(p, { replace: true })
  }

  function load() {
    api('/api/problems')
      .then(setProblems)
      .catch((e) => setError(e.message))
  }

  useEffect(load, [])

  const filtered = useMemo(() => {
    if (!problems) return []
    const t = q.trim().toLowerCase()
    return problems.filter(
      (p) =>
        (cat === 'all' || p.category === cat) &&
        (status === 'all' || p.status === status) &&
        (dup === 'all' || (dup === 'unique' ? !p.is_duplicate : !!p.is_duplicate)) &&
        (!t || (p.title + ' ' + p.description + ' ' + p.location).toLowerCase().includes(t))
    )
  }, [problems, q, cat, status, dup])

  if (error) return <div className="note note-error">Failed to load problems: {error}</div>
  if (!problems)
    return (
      <div className="page-loading">
        <span className="spinner" /> Loading your problems…
      </div>
    )

  const open = problems.filter((p) => p.status === 'open').length
  const assigned = problems.filter((p) => p.status === 'assigned' || p.status === 'in_review').length
  const dups = problems.filter((p) => p.is_duplicate).length
  const cats = [...new Set(problems.map((p) => p.category))].sort()

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Citizen Dashboard</h1>
          <p className="page-sub">Track the problems you reported and their AI analysis</p>
        </div>
        <Link to="/submit" className="btn btn-primary">
          <span aria-hidden="true">＋</span> Submit Problem
        </Link>
      </div>

      <div className="mini-stats">
        <div className="mini-stat">
          <span className="stat-icon">🧾</span>
          <div><b>{problems.length}</b><span>Total reported</span></div>
        </div>
        <div className="mini-stat">
          <span className="stat-icon">📌</span>
          <div><b>{open}</b><span>Open</span></div>
        </div>
        <div className="mini-stat">
          <span className="stat-icon">🎯</span>
          <div><b>{assigned}</b><span>In progress</span></div>
        </div>
        <div className="mini-stat">
          <span className="stat-icon">⚠️</span>
          <div><b className="dup-num">{dups}</b><span>Duplicates caught</span></div>
        </div>
      </div>

      {dup !== 'all' && (
        <div className="note note-info dup-banner">
          {dup === 'unique'
            ? <>Showing <b>unique problems only</b> — {filtered.length} of {problems.length} reports.</>
            : <>Showing <b>duplicate reports only</b> — {filtered.length} of {problems.length} reports (flagged by the AI).</>}
          <button className="dup-banner-clear" onClick={() => setDup('all')}>Show all ✕</button>
        </div>
      )}

      <div className="card">
        <div className="filters">
          <input
            className="search-input"
            placeholder="Search your problems…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <Select
            value={cat}
            onChange={setCat}
            options={[
              { value: 'all', label: 'All categories' },
              ...cats.map((c) => ({ value: c, label: c.replace(/_/g, ' ') })),
            ]}
          />
          <Select
            value={status}
            onChange={setStatus}
            options={[
              { value: 'all', label: 'All statuses' },
              { value: 'open', label: 'open' },
              { value: 'in_review', label: 'in_review' },
              { value: 'assigned', label: 'assigned' },
              { value: 'resolved', label: 'resolved' },
            ]}
          />
          <Select
            value={dup}
            onChange={setDup}
            options={[
              { value: 'all', label: 'All (unique + duplicates)' },
              { value: 'unique', label: 'Unique only' },
              { value: 'duplicates', label: 'Duplicates only' },
            ]}
          />
        </div>
      </div>

      <div className="card-list">
        {filtered.length === 0 && (
          <Empty>
            {problems.length === 0
              ? 'You have not reported any problems yet. Submit your first one to see the AI in action.'
              : 'No problems match your filters.'}
          </Empty>
        )}
        {filtered.map((p) => (
          <Link key={p.id} to={`/problem/${p.id}`} className="card problem-card">
            <div className="card-top">
              <h3>#{p.id} · {p.title}</h3>
              <div className="card-badges">
                <Badge tone={statusTone(p.status)}>{p.status.replace(/_/g, ' ')}</Badge>
                <Badge tone="blue">{p.category.replace(/_/g, ' ')}</Badge>
                <DuplicateBadge p={p} />
                {p.cluster && <Badge tone="teal">{p.cluster}</Badge>}
              </div>
            </div>
            <p className="card-text">{p.description.slice(0, 160)}{p.description.length > 160 ? '…' : ''}</p>
            <div className="card-meta">
              {p.location && <span className="meta-item" title={`Open ${p.location} in Google Maps`}>📍 {p.location}</span>}
              <span className="meta-item">🕒 {new Date(p.created_at).toLocaleDateString()}</span>
            </div>
          </Link>
        ))}
      </div>
    </>
  )
}
