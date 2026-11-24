import CityMap from '../components/CityMap.jsx'
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api.js'
import { Badge, DuplicateBadge, Empty, Select, statusLabel, statusTone } from '../components/ui.jsx'
import { IconChevronRight, IconClipboard, IconClock, IconFlag, IconMapPin, IconPlus, IconTarget, IconUsers, IconX } from '../components/icons.jsx'

export default function CitizenDashboard() {
  const [problems, setProblems] = useState(null)
  const [error, setError] = useState('')
  const [q, setQ] = useState('')
  const [cat, setCat] = useState('all')
  const [status, setStatus] = useState('all')
  const [viewMode, setViewMode] = useState('list')
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
        (!t || (p.title + ' ' + p.description + ' ' + p.location + ' ' + (p.assigned_team?.team_name || '')).toLowerCase().includes(t))
    )
  }, [problems, q, cat, status, dup])

  if (error) return <div className="note note-error">Sorry, we could not load your reports: {error}</div>
  if (!problems)
    return (
      <div className="page-loading">
        <span className="spinner" /> Loading your reports…
      </div>
    )

  const open = problems.filter((p) => p.status === 'open').length
  const assigned = problems.filter((p) => p.status === 'assigned' || p.status === 'in_review').length
  const cats = [...new Set(problems.map((p) => p.category))].sort()
  const moreFiltersOn = cat !== 'all' || dup !== 'all'

  const STATUS_TABS = [
    { value: 'all', label: 'All' },
    { value: 'open', label: statusLabel('open') },
    { value: 'in_review', label: statusLabel('in_review') },
    { value: 'assigned', label: statusLabel('assigned') },
    { value: 'resolved', label: statusLabel('resolved') },
  ]

  return (
    <>
      <div className="page-head">
        <div>
          <h1>My Reports</h1>
          <p className="page-sub">Here are the problems you reported and what is happening with each one.</p>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <div className="seg" role="group" aria-label="View mode">
            <button
              type="button"
              className={'seg-btn' + (viewMode === 'list' ? ' active' : '')}
              onClick={() => setViewMode('list')}
            >
              List View
            </button>
            <button
              type="button"
              className={'seg-btn' + (viewMode === 'map' ? ' active' : '')}
              onClick={() => setViewMode('map')}
            >
              <IconMapPin size={15} /> Map View
            </button>
          </div>
          <Link to="/submit" className="btn btn-primary btn-lg">
            <IconPlus size={20} aria-hidden="true" /> Report a Problem
          </Link>
        </div>
      </div>

      <div className="mini-stats">
        <div className="mini-stat mine-blue">
          <span className="stat-icon" aria-hidden="true"><IconClipboard /></span>
          <div><b>{problems.length}</b><span>Reports sent</span></div>
        </div>
        <div className="mini-stat mine-green">
          <span className="stat-icon" aria-hidden="true"><IconFlag /></span>
          <div><b>{open}</b><span>New</span></div>
        </div>
        <div className="mini-stat mine-amber">
          <span className="stat-icon" aria-hidden="true"><IconTarget /></span>
          <div><b>{assigned}</b><span>Being handled</span></div>
        </div>
      </div>

      {dup !== 'all' && (
        <div className="note note-info dup-banner">
          {dup === 'unique'
            ? <>Showing <b>reports that are not copies</b> — {filtered.length} of {problems.length}.</>
            : <>Showing <b>reports already reported before</b> — {filtered.length} of {problems.length}.</>}
          <button className="dup-banner-clear" onClick={() => setDup('all')}>Show all <IconX size={14} /></button>
        </div>
      )}

      <div className="card filter-card">
        <label className="field-label" htmlFor="report-search">Search your reports</label>
        <input
          id="report-search"
          className="search-input"
          placeholder="Type a word, for example “road”"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />

        <div className="field-label" id="status-label">Show</div>
        <div className="seg" role="group" aria-labelledby="status-label">
          {STATUS_TABS.map((t) => (
            <button
              key={t.value}
              type="button"
              className={'seg-btn' + (status === t.value ? ' active' : '')}
              aria-pressed={status === t.value}
              onClick={() => setStatus(t.value)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <details className="more-filters" open={moreFiltersOn || undefined}>
          <summary>More ways to filter</summary>
          <div className="filters">
            <Select
              value={cat}
              onChange={setCat}
              options={[
                { value: 'all', label: 'All kinds of problem' },
                ...cats.map((c) => ({ value: c, label: c.replace(/_/g, ' ') })),
              ]}
            />
            <Select
              value={dup}
              onChange={setDup}
              options={[
                { value: 'all', label: 'Show everything' },
                { value: 'unique', label: 'Not copies of another report' },
                { value: 'duplicates', label: 'Already reported before' },
              ]}
            />
          </div>
        </details>
      </div>

      <div className="card-list">
        {filtered.length === 0 && (
          <Empty>
            {problems.length === 0
              ? 'You have not reported anything yet. Press “Report a Problem” to send your first one.'
              : 'No reports match what you chose. Try “All” above.'}
          </Empty>
        )}
        {filtered.map((p) => (
          <Link key={p.id} to={`/problem/${p.id}`} className="card problem-card">
            <div className="card-top">
              <h3>{p.title}</h3>
              <div className="card-badges">
                <Badge tone={statusTone(p.status)}>{statusLabel(p.status)}</Badge>
                {p.assigned_team && (
                  <Badge tone="green">Team: {p.assigned_team.team_name}</Badge>
                )}
                <DuplicateBadge p={p} />
              </div>
            </div>
            <p className="card-text">{p.description.slice(0, 160)}{p.description.length > 160 ? '…' : ''}</p>
            <div className="card-meta">
              <span className="meta-item">Report #{p.id}</span>
              {p.assigned_team && (
                <span className="meta-item" style={{ color: 'var(--ok, #16a34a)', fontWeight: 600 }}>
                  <IconUsers size={18} /> {p.assigned_team.team_name}
                </span>
              )}
              {p.location && <span className="meta-item"><IconMapPin size={18} /> {p.location}</span>}
              <span className="meta-item"><IconClock size={18} /> {new Date(p.created_at).toLocaleDateString()}</span>
            </div>
            <span className="card-open">Open this report <IconChevronRight size={18} /></span>
          </Link>
        ))}
      </div>
    </>
  )
}
