#!/usr/bin/env python3
"""TASK 11 — replace emoji glyphs with the central SVG icon set (one pass, verified)."""
import sys, pathlib

ROOT = pathlib.Path(__file__).parent / 'src'
failures = []
applied = 0

def rep(rel, pairs):
    """pairs: list of (old, new, count_expected). count_expected 0 = replace-all."""
    global applied
    p = ROOT / rel
    t = p.read_text()
    for old, new, n in pairs:
        c = t.count(old)
        if n == 0:
            if c == 0:
                failures.append(f"{rel}: NOT FOUND (replace-all): {old[:70]!r}")
                continue
            t = t.replace(old, new)
            applied += c
        else:
            if c != n:
                failures.append(f"{rel}: expected {n} of {old[:70]!r}, found {c}")
                continue
            t = t.replace(old, new, n)
            applied += n
    p.write_text(t)

# ---------------- App.jsx ----------------
rep('App.jsx', [(
""">      <div className="bg-glow" aria-hidden="true">
        <i className="glow glow-1" />
        <i className="glow glow-2" />
        <i className="glow glow-3" />
      </div>
      <Routes>""",
""">      <Routes>""", 1)])

# ---------------- toast.jsx ----------------
rep('toast.jsx', [(
"import { createContext, useCallback, useContext, useState } from 'react'",
"import { createContext, useCallback, useContext, useState } from 'react'\nimport { IconCheckCircle, IconAlert } from './components/icons.jsx'", 1), (
"""        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.tone}`}>
            {t.message}
          </div>
        ))}""",
"""        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.tone}`}>
            <span aria-hidden="true">{t.tone === 'error' ? <IconAlert size={16} /> : <IconCheckCircle size={16} />}</span>
            <span>{t.message}</span>
          </div>
        ))}""", 1)])

# ---------------- ui.jsx ----------------
rep('components/ui.jsx', [(
"import { createPortal } from 'react-dom'",
"import { createPortal } from 'react-dom'\nimport { IconAlert, IconMapPin } from './icons.jsx'", 1), (
"""      <span className="badge badge-red" title="Flagged as a probable duplicate by the trained classifier">
        ⚠️ Duplicate{pct != null ? ` · ${pct}%` : ''}
      </span>""",
"""      <span className="badge badge-red" title="Flagged as a probable duplicate by the trained classifier">
        <IconAlert size={13} /> Duplicate{pct != null ? ` · ${pct}%` : ''}
      </span>""", 1), (
"""      <span className="loc-pin" aria-hidden="true">📍</span>""",
"""      <span className="loc-pin" aria-hidden="true"><IconMapPin size={15} /></span>""", 1)])

# ---------------- Layout.jsx ----------------
rep('components/Layout.jsx', [(
"import NotificationBell from './NotificationBell.jsx'",
"import NotificationBell from './NotificationBell.jsx'\nimport { IconBack, IconChart, IconClipboard, IconEdit, IconFwd, IconHome, IconLogout, IconMoon, IconSun, IconTarget, IconUser, IconUsers } from './icons.jsx'", 1), (
"""/* ---------- small inline SVG icons (crisp at any size, theme-aware) ---------- */
const IconMenu = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <line x1="4" y1="7" x2="20" y2="7" /><line x1="4" y1="12" x2="20" y2="12" /><line x1="4" y1="17" x2="20" y2="17" />
  </svg>
)
const IconBack = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" />
  </svg>
)
const IconFwd = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" />
  </svg>
)
""", "", 1), (
"        { to: '/dashboard', label: 'My Problems', icon: '📋' },",
"        { to: '/dashboard', label: 'My Problems', icon: IconClipboard },", 1), (
"        { to: '/submit', label: 'Submit Problem', icon: '📝' },",
"        { to: '/submit', label: 'Submit Problem', icon: IconEdit },", 1), (
"        ...(user.role === 'citizen' ? [{ to: '/teams', label: 'Teams Directory', icon: '👥' }] : []),",
"        ...(user.role === 'citizen' ? [{ to: '/teams', label: 'Teams Directory', icon: IconUsers }] : []),", 1), (
"        { to: '/team', label: 'Team Home', icon: '🏠', end: true },",
"        { to: '/team', label: 'Team Home', icon: IconHome, end: true },", 1), (
"        { to: '/team/recommended', label: 'Recommended', icon: '🎯' },",
"        { to: '/team/recommended', label: 'Recommended', icon: IconTarget },", 1), (
"        { to: '/teams', label: 'Teams Directory', icon: '👥' },",
"        { to: '/teams', label: 'Teams Directory', icon: IconUsers },", 1), (
"        items: [{ to: '/admin', label: 'Admin Dashboard', icon: '📊' }],",
"        items: [{ to: '/admin', label: 'Admin Dashboard', icon: IconChart }],", 1), (
"        items: [{ to: '/profile', label: 'My Profile', icon: '👤', end: true }],",
"        items: [{ to: '/profile', label: 'My Profile', icon: IconUser, end: true }],", 1), (
"""              >
                <span className="nav-icon">{l.icon}</span>""",
"""              >
                <span className="nav-icon" aria-hidden="true">{l.icon ? <l.icon size={18} /> : null}</span>""", 1), (
"""      <span className={theme === 'dark' ? 'theme-icon sun' : 'theme-icon moon'}>
        {theme === 'dark' ? '☀️' : '🌙'}
      </span>""",
"""      <span className="theme-icon" aria-hidden="true">
        {theme === 'dark' ? <IconSun size={18} /> : <IconMoon size={18} />}
      </span>""", 1), (
"""          <button className="btn btn-ghost btn-block" onClick={onLogout}>
            Log out
          </button>""",
"""          <button className="btn btn-ghost btn-block" onClick={onLogout}>
            <IconLogout size={15} /> Log out
          </button>""", 1)])

# ---------------- NotificationBell.jsx ----------------
rep('components/NotificationBell.jsx', [(
"import { useAuth } from '../auth.jsx'",
"import { useAuth } from '../auth.jsx'\nimport { IconBell, IconBellOff, IconCheck, IconLink, IconLogout, IconMessage } from './icons.jsx'", 1), (
"""const TYPE_META = {
  message: { icon: '💬', label: 'Message' },
  team_deleted: { icon: '🚪', label: 'Team update' },
  match_decision: { icon: '🤝', label: 'Decision' },
}""",
"""const TYPE_META = {
  message: { icon: IconMessage, label: 'Message' },
  team_deleted: { icon: IconLogout, label: 'Team update' },
  match_decision: { icon: IconLink, label: 'Decision' },
}""", 1), (
"""        <span className="notif-bell-icon" aria-hidden="true">🔔</span>""",
"""        <span className="notif-bell-icon" aria-hidden="true"><IconBell size={18} /></span>""", 1), (
"""                <div className="notif-empty">🔕 You&apos;re all caught up.</div>""",
"""                <div className="notif-empty"><IconBellOff size={16} /> You&apos;re all caught up.</div>""", 1), (
"""                const meta = TYPE_META[n.type] || { icon: '🔔', label: 'Notice' }""",
"""                const meta = TYPE_META[n.type] || { icon: IconBell, label: 'Notice' }""", 1), (
"""                    <span className="notif-ico" aria-hidden="true">{meta.icon}</span>""",
"""                    <span className="notif-ico" aria-hidden="true"><meta.icon size={16} /></span>""", 1), (
"""                <button className="notif-markall" onClick={markAll}>
                  Mark all read
                </button>""",
"""                <button className="notif-markall" onClick={markAll}>
                  <IconCheck size={13} /> Mark all read
                </button>""", 1)])

# ---------------- DataLabels.jsx ----------------
rep('components/DataLabels.jsx', [(
"import { Badge, Empty, Spinner } from './ui.jsx'",
"import { Badge, Empty, Spinner } from './ui.jsx'\nimport { IconBack, IconCheck, IconCpu, IconFwd, IconPlus, IconX } from './icons.jsx'", 1), (
"toast.push(isDuplicate ? '✓ Marked as duplicate' : '✓ Marked as not a duplicate')",
"toast.push(isDuplicate ? 'Marked as duplicate' : 'Marked as not a duplicate')", 1), (
"""          <button className="btn btn-outline btn-sm" disabled={!!busy} onClick={mine}>
            {busy === 'mine' ? 'Mining…' : '＋ Mine more candidates'}
          </button>
          <button className="btn btn-primary btn-sm" disabled={!!busy} onClick={train}>
            {busy === 'train' ? 'Training…' : '▶ Train models now'}
          </button>""",
"""          <button className="btn btn-outline btn-sm" disabled={!!busy} onClick={mine}>
            {busy === 'mine' ? 'Mining…' : <><IconPlus size={14} /> Mine more candidates</>}
          </button>
          <button className="btn btn-primary btn-sm" disabled={!!busy} onClick={train}>
            {busy === 'train' ? 'Training…' : <><IconCpu size={14} /> Train models now</>}
          </button>""", 1), (
"""                  <button className="btn btn-primary btn-sm" onClick={() => labelPair(p, true)}>✓ Duplicate</button>
                  <button className="btn btn-outline btn-sm" onClick={() => labelPair(p, false)}>✗ Not a duplicate</button>""",
"""                  <button className="btn btn-primary btn-sm" onClick={() => labelPair(p, true)}><IconCheck size={14} /> Duplicate</button>
                  <button className="btn btn-outline btn-sm" onClick={() => labelPair(p, false)}><IconX size={14} /> Not a duplicate</button>""", 1), (
"""              onClick={() => { setPairOffset(pairOffset - 5); loadPairs(pairOffset - 5) }}>← Prev</button>""",
"""              onClick={() => { setPairOffset(pairOffset - 5); loadPairs(pairOffset - 5) }}><IconBack size={13} /> Prev</button>""", 1), (
"""              onClick={() => { setPairOffset(pairOffset + 5); loadPairs(pairOffset + 5) }}>Next →</button>""",
"""              onClick={() => { setPairOffset(pairOffset + 5); loadPairs(pairOffset + 5) }}>Next <IconFwd size={13} /></button>""", 1), (
"""                    title={t.relevant == null ? 'Click to mark relevant / not relevant' : 'Click to toggle'}>
                    {t.relevant === 1 ? '✓ ' : t.relevant === 0 ? '✗ ' : '· '}
                    {t.team_name}
                  </button>""",
"""                    title={t.relevant == null ? 'Click to mark relevant / not relevant' : 'Click to toggle'}>
                    {t.relevant === 1 ? <IconCheck size={13} /> : t.relevant === 0 ? <IconX size={13} /> : '·'}
                    {t.team_name}
                  </button>""", 1), (
"""              onClick={() => { setRelOffset(relOffset - 3); loadRel(relView, relOffset - 3) }}>← Prev</button>""",
"""              onClick={() => { setRelOffset(relOffset - 3); loadRel(relView, relOffset - 3) }}><IconBack size={13} /> Prev</button>""", 1), (
"""              onClick={() => { setRelOffset(relOffset + 3); loadRel(relView, relOffset + 3) }}>Next →</button>""",
"""              onClick={() => { setRelOffset(relOffset + 3); loadRel(relView, relOffset + 3) }}>Next <IconFwd size={13} /></button>""", 1)])

# ---------------- Landing.jsx ----------------
rep('pages/Landing.jsx', [(
"import { useTheme } from '../theme.jsx'",
"import { useTheme } from '../theme.jsx'\nimport { IconChart, IconGraduationCap, IconLayers, IconMoon, IconRefresh, IconSparkles, IconSun, IconUsers } from '../components/icons.jsx'", 1), (
"""  { icon: '🔁', title: 'Duplicate detection',""",
"""  { icon: IconRefresh, title: 'Duplicate detection',""", 1), (
"""  { icon: '🧠', title: 'Semantic understanding',""",
"""  { icon: IconSparkles, title: 'Semantic understanding',""", 1), (
"""  { icon: '📦', title: 'Automatic clustering',""",
"""  { icon: IconLayers, title: 'Automatic clustering',""", 1), (
"""  { icon: '🎓', title: 'Student-team matching',""",
"""  { icon: IconGraduationCap, title: 'Student-team matching',""", 1), (
"""  { icon: '📊', title: 'Measurable AI',""",
"""  { icon: IconChart, title: 'Measurable AI',""", 1), (
"""  { icon: '👥', title: 'Feedback loop',""",
"""  { icon: IconUsers, title: 'Feedback loop',""", 1), (
"""            <span className={theme === 'dark' ? 'theme-icon sun' : 'theme-icon moon'}>
              {theme === 'dark' ? '☀️' : '🌙'}
            </span>""",
"""            <span className="theme-icon" aria-hidden="true">
              {theme === 'dark' ? <IconSun size={18} /> : <IconMoon size={18} />}
            </span>""", 1), (
"""          <span className="hero-badge">🧠 AI/ML civic platform · live trained models</span>""",
"""          <span className="hero-badge"><IconSparkles size={15} /> AI/ML civic platform · live trained models</span>""", 1), (
"""            <div className="feature-icon">{f.icon}</div>""",
"""            <div className="feature-icon" aria-hidden="true"><f.icon size={21} /></div>""", 1)])

# ---------------- AdminDashboard.jsx ----------------
rep('pages/AdminDashboard.jsx', [(
"} from 'recharts'",
"} from 'recharts'\nimport { IconAlert, IconCheckCircle, IconClipboard, IconCpu, IconLayers, IconRefresh, IconUsers } from '../components/icons.jsx'", 1), (
"""        <StatCard label="Total problems" value={stats.total_problems} tone="blue" icon="🧾\"""",
"""        <StatCard label="Total problems" value={stats.total_problems} tone="blue" icon={<IconClipboard />}\"""", 1), (
"""        <StatCard label="Unique problems" value={stats.unique_problems} tone="green" icon="✅\"""",
"""        <StatCard label="Unique problems" value={stats.unique_problems} tone="green" icon={<IconCheckCircle />}\"""", 1), (
"""          tone="red" icon="⚠️\"""",
"""          tone="red" icon={<IconAlert />}\"""", 1), (
"""        <StatCard label="Clusters" value={stats.clusters} tone="violet" icon="📦\"""",
"""        <StatCard label="Clusters" value={stats.clusters} tone="violet" icon={<IconLayers />}\"""", 1), (
"""        <StatCard label="Registered teams" value={stats.registered_teams} tone="amber" icon="👥\"""",
"""        <StatCard label="Registered teams" value={stats.registered_teams} tone="amber" icon={<IconUsers />}\"""", 1), (
"""          tone="teal" icon="🤖\"""",
"""          tone="teal" icon={<IconCpu />}\"""", 1), (
"""        <button className="btn btn-ghost btn-sm" onClick={load}>↻ Refresh</button>""",
"""        <button className="btn btn-ghost btn-sm" onClick={load}><IconRefresh size={14} /> Refresh</button>""", 1)])

# ---------------- CitizenDashboard.jsx ----------------
rep('pages/CitizenDashboard.jsx', [(
"import { Badge, DuplicateBadge, Empty, Select, statusTone } from '../components/ui.jsx'",
"import { Badge, DuplicateBadge, Empty, Select, statusTone } from '../components/ui.jsx'\nimport { IconAlert, IconClipboard, IconClock, IconFlag, IconMapPin, IconPlus, IconTarget, IconX } from '../components/icons.jsx'", 1), (
"""        <Link to="/submit" className="btn btn-primary">
          <span aria-hidden="true">＋</span> Submit Problem
        </Link>""",
"""        <Link to="/submit" className="btn btn-primary">
          <IconPlus size={16} aria-hidden="true" /> Submit Problem
        </Link>""", 1), (
"""        <div className="mini-stat">
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
        </div>""",
"""        <div className="mini-stat mine-blue">
          <span className="stat-icon" aria-hidden="true"><IconClipboard /></span>
          <div><b>{problems.length}</b><span>Total reported</span></div>
        </div>
        <div className="mini-stat mine-green">
          <span className="stat-icon" aria-hidden="true"><IconFlag /></span>
          <div><b>{open}</b><span>Open</span></div>
        </div>
        <div className="mini-stat mine-amber">
          <span className="stat-icon" aria-hidden="true"><IconTarget /></span>
          <div><b>{assigned}</b><span>In progress</span></div>
        </div>
        <div className="mini-stat mine-red">
          <span className="stat-icon" aria-hidden="true"><IconAlert /></span>
          <div><b className="dup-num">{dups}</b><span>Duplicates caught</span></div>
        </div>""", 1), (
"""          <button className="dup-banner-clear" onClick={() => setDup('all')}>Show all ✕</button>""",
"""          <button className="dup-banner-clear" onClick={() => setDup('all')}>Show all <IconX size={12} /></button>""", 1), (
"""              {p.location && <span className="meta-item" title={`Open ${p.location} in Google Maps`}>📍 {p.location}</span>}
              <span className="meta-item">🕒 {new Date(p.created_at).toLocaleDateString()}</span>""",
"""              {p.location && <span className="meta-item" title={`Open ${p.location} in Google Maps`}><IconMapPin size={14} /> {p.location}</span>}
              <span className="meta-item"><IconClock size={14} /> {new Date(p.created_at).toLocaleDateString()}</span>""", 1)])

# ---------------- SubmitProblem.jsx ----------------
rep('pages/SubmitProblem.jsx', [(
"import { ErrorNote, LocationButton, ScoreBar } from '../components/ui.jsx'",
"import { ErrorNote, LocationButton, ScoreBar } from '../components/ui.jsx'\nimport { IconAlert, IconBack, IconBox, IconCheck, IconCheckCircle, IconClock, IconCpu, IconEdit, IconFileText, IconGraduationCap, IconLayers, IconMapPin, IconRefresh } from '../components/icons.jsx'", 1), (
"""  { icon: '📝', label: 'NLP preprocessing', detail: 'tokenize · stop-words · normalize' },
  { icon: '🧠', label: 'Semantic embedding', detail: 'sentence-transformers 384-d vector' },
  { icon: '🔁', label: 'Duplicate detection', detail: 'cosine vs all reports, tuned threshold' },
  { icon: '📦', label: 'Clustering', detail: 'K-Means with auto k (silhouette)' },
  { icon: '🎓', label: 'Team matching', detail: 'skills + interests + experience' }""",
"""  { icon: IconEdit, label: 'NLP preprocessing', detail: 'tokenize · stop-words · normalize' },
  { icon: IconCpu, label: 'Semantic embedding', detail: 'sentence-transformers 384-d vector' },
  { icon: IconRefresh, label: 'Duplicate detection', detail: 'cosine vs all reports, tuned threshold' },
  { icon: IconLayers, label: 'Clustering', detail: 'K-Means with auto k (silhouette)' },
  { icon: IconGraduationCap, label: 'Team matching', detail: 'skills + interests + experience' }""", 1), (
"""          <h1>Problem submitted ✓</h1>
          <Link to="/dashboard" className="btn btn-ghost">← Back to my problems</Link>""",
"""          <h1>Problem submitted</h1>
          <Link to="/dashboard" className="btn btn-ghost"><IconBack size={14} /> Back to my problems</Link>""", 1), (
"""          <div className="note note-warn">
            ⚠️ <b>Looks like a duplicate.</b> Very similar to""",
"""          <div className="note note-warn">
            <IconAlert size={16} /> <b>Looks like a duplicate.</b> Very similar to""", 1), (
"""          <div className="note note-ok">
            ✅ No duplicate found — stored as a <b>unique</b> problem.
          </div>""",
"""          <div className="note note-ok">
            <IconCheckCircle size={16} /> No duplicate found — stored as a <b>unique</b> problem.
          </div>""", 1), (
"""            <div className="card-meta">
              <span>🗂 {p.category}</span>
              <span>🕒 {new Date(p.created_at).toLocaleDateString()}</span>
            </div>""",
"""            <div className="card-meta">
              <span className="meta-item"><IconFileText size={14} /> {p.category}</span>
              <span className="meta-item"><IconClock size={14} /> {new Date(p.created_at).toLocaleDateString()}</span>
            </div>""", 1), (
"""                  <div className="loc-label">📍 Reported location</div>""",
"""                  <div className="loc-label"><IconMapPin size={14} /> Reported location</div>""", 1), (
"""            {p.cluster && <div className="note note-info">📦 Clustered into <b>{p.cluster}</b></div>}
            <Link to={`/problem/${p.id}`} className="btn btn-primary btn-sm">
              View full AI analysis →
            </Link>""",
"""            {p.cluster && <div className="note note-info"><IconBox size={15} /> Clustered into <b>{p.cluster}</b></div>}
            <Link to={`/problem/${p.id}`} className="btn btn-primary btn-sm">
              View full AI analysis
            </Link>""", 1), (
"""              <span className="step-icon">{i < step ? '✓' : s.icon}</span>""",
"""              <span className="step-icon" aria-hidden="true">{i < step ? <IconCheck size={16} /> : <s.icon size={16} />}</span>""", 1)])

# ---------------- ProblemDetail.jsx ----------------
rep('pages/ProblemDetail.jsx', [(
"import { Badge, DuplicateBadge, ErrorNote, LocationButton, ScoreBar, Select, Spinner, statusTone } from '../components/ui.jsx'",
"import { Badge, DuplicateBadge, ErrorNote, LocationButton, ScoreBar, Select, Spinner, statusTone } from '../components/ui.jsx'\nimport { IconAlert, IconBack, IconBox, IconCheck, IconClock, IconFileText, IconGraduationCap, IconMagnet, IconMapPin, IconRefresh, IconThumbsDown, IconThumbsUp, IconX } from '../components/icons.jsx'", 1), (
"""      toast.push(`Feedback recorded: ${type === 'good_match' ? 'good match 👍' : 'bad match 👎'}`)""",
"""      toast.push(`Feedback recorded: ${type === 'good_match' ? 'good match' : 'bad match'}`)""", 1), (
"""          ? 'Thanks — confirmed the duplicate flag 👍'
          : 'Thanks — flagged the duplicate decision for review'""",
"""          ? 'Thanks — confirmed the duplicate flag'
          : 'Thanks — flagged the duplicate decision for review'""", 1), (
"""          <p className="muted"><Link to="/dashboard">← back to my problems</Link></p>""",
"""          <p className="muted"><Link to="/dashboard"><IconBack size={13} /> back to my problems</Link></p>""", 1), (
"""        <div className="note note-warn">
          ⚠️ Flagged as a <b>duplicate</b> of{' '}""",
"""        <div className="note note-warn">
          <IconAlert size={16} /> Flagged as a <b>duplicate</b> of{' '}""", 1), (
"""              <button className="btn btn-ghost btn-sm" onClick={() => sendDuplicateFeedback(true)}>
                ✓ yes, duplicate
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => sendDuplicateFeedback(false)}>
                ✕ not a duplicate
              </button>""",
"""              <button className="btn btn-ghost btn-sm" onClick={() => sendDuplicateFeedback(true)}>
                <IconCheck size={13} /> yes, duplicate
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => sendDuplicateFeedback(false)}>
                <IconX size={13} /> not a duplicate
              </button>""", 1), (
"""          <span className="ai-strip-icon">🔁</span>""",
"""          <span className="ai-strip-icon" aria-hidden="true"><IconRefresh size={19} /></span>""", 1), (
"""          <span className="ai-strip-icon">📦</span>""",
"""          <span className="ai-strip-icon" aria-hidden="true"><IconBox size={19} /></span>""", 1), (
"""          <span className="ai-strip-icon">🧲</span>""",
"""          <span className="ai-strip-icon" aria-hidden="true"><IconMagnet size={19} /></span>""", 1), (
"""          <span className="ai-strip-icon">🎓</span>""",
"""          <span className="ai-strip-icon" aria-hidden="true"><IconGraduationCap size={19} /></span>""", 1), (
"""            <span>📦 cluster: {p.cluster || '—'}</span>
            <span>🕒 {new Date(p.created_at).toLocaleString()}</span>""",
"""            <span className="meta-item"><IconBox size={14} /> cluster: {p.cluster || '—'}</span>
            <span className="meta-item"><IconClock size={14} /> {new Date(p.created_at).toLocaleString()}</span>""", 1), (
"""                <div className="loc-label">📍 Reported location</div>""",
"""                <div className="loc-label"><IconMapPin size={14} /> Reported location</div>""", 1), (
"""                      <button className="btn btn-ghost btn-sm" onClick={() => sendFeedback(t.match_id, 'good_match')}>👍</button>
                      <button className="btn btn-ghost btn-sm" onClick={() => sendFeedback(t.match_id, 'bad_match')}>👎</button>""",
"""                      <button className="btn btn-ghost btn-sm" onClick={() => sendFeedback(t.match_id, 'good_match')} aria-label="Good match"><IconThumbsUp size={14} /></button>
                      <button className="btn btn-ghost btn-sm" onClick={() => sendFeedback(t.match_id, 'bad_match')} aria-label="Bad match"><IconThumbsDown size={14} /></button>""", 1)])

# ---------------- Profile.jsx ----------------
rep('pages/Profile.jsx', [(
"import { Badge, ErrorNote } from '../components/ui.jsx'",
"import { Badge, ErrorNote } from '../components/ui.jsx'\nimport { IconCopy, IconInfo } from '../components/icons.jsx'", 1), (
"""<button className="copy-btn" onClick={() => copy(me.email, 'Email')} title="Copy email">⧉ copy</button>""",
"""<button className="copy-btn" onClick={() => copy(me.email, 'Email')} title="Copy email"><IconCopy size={13} /> copy</button>""", 1), (
"""<button className="copy-btn" onClick={() => copy(String(me.id), 'User ID')} title="Copy ID">⧉ copy</button>""",
"""<button className="copy-btn" onClick={() => copy(String(me.id), 'User ID')} title="Copy ID"><IconCopy size={13} /> copy</button>""", 1), (
"""            <span aria-hidden="true">ℹ️</span>""",
"""            <span aria-hidden="true"><IconInfo size={16} /></span>""", 1)])

# ---------------- TeamDashboard.jsx ----------------
rep('pages/TeamDashboard.jsx', [(
"import { ErrorNote } from '../components/ui.jsx'",
"import { ErrorNote } from '../components/ui.jsx'\nimport { IconChevronRight, IconCpu, IconHeart, IconLogout, IconPlus, IconSliders, IconUsers, IconX } from '../components/icons.jsx'", 1), (
"toast.push('✓ Team profile saved — matching now uses the new skills & interests')",
"toast.push('Team profile saved — matching now uses the new skills & interests')", 1), (
"""        <Link to="/team/recommended" className="btn btn-outline">View recommendations →</Link>""",
"""        <Link to="/team/recommended" className="btn btn-outline">View recommendations <IconChevronRight size={14} /></Link>""", 1), (
"""          <span className="tdb-ico" aria-hidden="true">🚪</span>""",
"""          <span className="tdb-ico" aria-hidden="true"><IconLogout size={22} /></span>""", 1), (
"""          >
            ✕
          </button>""",
"""          >
            <IconX size={16} />
          </button>""", 1), (
"""                <button type="button" className="btn btn-ghost btn-sm" onClick={() => removeMember(i)}>✕</button>""",
"""                <button type="button" className="btn btn-ghost btn-sm" onClick={() => removeMember(i)} aria-label="Remove member"><IconX size={14} /></button>""", 1), (
"""            + Add member
          </button>""",
"""            <IconPlus size={14} /> Add member
          </button>""", 1), (
"""            {form.skills.split(',').map((s) => s.trim()).filter(Boolean).map((s) => (
              <span className="kw" key={`s-${s}`}>⚙ {s}</span>
            ))}
            {form.interests.split(',').map((s) => s.trim()).filter(Boolean).map((s) => (
              <span className="kw kw-interest" key={`i-${s}`}>❤ {s}</span>
            ))}""",
"""            {form.skills.split(',').map((s) => s.trim()).filter(Boolean).map((s) => (
              <span className="kw" key={`s-${s}`}><IconSliders size={12} /> {s}</span>
            ))}
            {form.interests.split(',').map((s) => s.trim()).filter(Boolean).map((s) => (
              <span className="kw kw-interest" key={`i-${s}`}><IconHeart size={12} /> {s}</span>
            ))}""", 1), (
"""              <span>👥 {team.members.length} members</span>
              <span>🤖 team id: {team.id}</span>""",
"""              <span className="meta-item"><IconUsers size={14} /> {team.members.length} members</span>
              <span className="meta-item"><IconCpu size={14} /> team id: {team.id}</span>""", 1)])

# ---------------- TeamDetail.jsx ----------------
rep('pages/TeamDetail.jsx', [(
"import { Badge, ErrorNote, Spinner } from '../components/ui.jsx'",
"import { Badge, ErrorNote, Spinner } from '../components/ui.jsx'\nimport { IconAward, IconEdit, IconHeart, IconInfo, IconSliders, IconTarget, IconUsers } from '../components/icons.jsx'", 1), (
"""              <Link to="/team" className="btn btn-primary btn-sm">✎ Edit team profile</Link>""",
"""              <Link to="/team" className="btn btn-primary btn-sm"><IconEdit size={14} /> Edit team profile</Link>""", 1), (
"""              <Link to="/team/recommended" className="btn btn-outline btn-sm">🎯 View recommendations</Link>""",
"""              <Link to="/team/recommended" className="btn btn-outline btn-sm"><IconTarget size={14} /> View recommendations</Link>""", 1), (
"""        <div className="team-detail-avatar" aria-hidden="true">👥</div>""",
"""        <div className="team-detail-avatar" aria-hidden="true"><IconUsers size={34} /></div>""", 1), (
"""            <p className="muted small" style={{ margin: 0 }}>🏆 {team.experience}</p>""",
"""            <p className="muted small" style={{ margin: 0 }}><IconAward size={14} /> {team.experience}</p>""", 1), (
"""            <span aria-hidden="true">ℹ️</span>""",
"""            <span aria-hidden="true"><IconInfo size={16} /></span>""", 1), (
"""            {team.skills.map((s) => (
              <span className="kw" key={`s-${s}`}>⚙ {s}</span>
            ))}""",
"""            {team.skills.map((s) => (
              <span className="kw" key={`s-${s}`}><IconSliders size={12} /> {s}</span>
            ))}""", 1), (
"""            {team.interests.map((s) => (
              <span className="kw kw-interest" key={`i-${s}`}>❤ {s}</span>
            ))}""",
"""            {team.interests.map((s) => (
              <span className="kw kw-interest" key={`i-${s}`}><IconHeart size={12} /> {s}</span>
            ))}""", 1)])

# ---------------- TeamRecommended.jsx ----------------
rep('pages/TeamRecommended.jsx', [(
"import { Badge, Empty, ErrorNote, LocationButton, ScoreBar, Spinner } from '../components/ui.jsx'",
"import { Badge, Empty, ErrorNote, LocationButton, ScoreBar, Spinner } from '../components/ui.jsx'\nimport { IconCheck, IconCpu, IconMapPin, IconThumbsDown, IconThumbsUp, IconX } from '../components/icons.jsx'", 1), (
"""          ? `✓ Problem accepted — status is now “${r.problem_status}”`""",
"""          ? `Problem accepted — status is now “${r.problem_status}”`""", 1), (
"""      toast.push(`Feedback recorded: ${type === 'good_match' ? 'good rec 👍' : 'bad rec 👎'}`)""",
"""      toast.push(`Feedback recorded: ${type === 'good_match' ? 'good rec' : 'bad rec'}`)""", 1), (
"""              {r.location && <span className="meta-item">📍 {r.location}</span>}
              <span className="meta-item">🤖 relevance</span>""",
"""              {r.location && <span className="meta-item"><IconMapPin size={14} /> {r.location}</span>}
              <span className="meta-item"><IconCpu size={14} /> relevance</span>""", 1), (
"""                <button className="btn btn-primary btn-sm" onClick={() => decide(r.match_id, 'accept')}>
                  ✓ Accept problem
                </button>
                <button className="btn btn-ghost btn-sm" onClick={() => decide(r.match_id, 'reject')}>
                  ✕ Not for us
                </button>
                <span className="fb-buttons">
                  <button className="btn btn-ghost btn-sm" onClick={() => feedback(r.match_id, 'good_match')}>👍 good rec</button>
                  <button className="btn btn-ghost btn-sm" onClick={() => feedback(r.match_id, 'bad_match')}>👎 bad rec</button>
                </span>""",
"""                <button className="btn btn-primary btn-sm" onClick={() => decide(r.match_id, 'accept')}>
                  <IconCheck size={14} /> Accept problem
                </button>
                <button className="btn btn-ghost btn-sm" onClick={() => decide(r.match_id, 'reject')}>
                  <IconX size={14} /> Not for us
                </button>
                <span className="fb-buttons">
                  <button className="btn btn-ghost btn-sm" onClick={() => feedback(r.match_id, 'good_match')}><IconThumbsUp size={13} /> good rec</button>
                  <button className="btn btn-ghost btn-sm" onClick={() => feedback(r.match_id, 'bad_match')}><IconThumbsDown size={13} /> bad rec</button>
                </span>""", 1)])

# ---------------- TeamsDirectory.jsx ----------------
rep('pages/TeamsDirectory.jsx', [(
"import { Badge, Empty, ErrorNote, Spinner } from '../components/ui.jsx'",
"import { Badge, Empty, ErrorNote, Spinner } from '../components/ui.jsx'\nimport { IconAward, IconHeart, IconSliders, IconTrash } from '../components/icons.jsx'", 1), (
"""      toast.push(`🗑 Team “${t.team_name}” removed from the directory`)""",
"""      toast.push(`Team “${t.team_name}” removed from the directory`)""", 1), (
"""      toast.push('⚠️ Could not delete team: ' + err.message)""",
"""      toast.push('Could not delete team: ' + err.message)""", 1), (
"""          placeholder="🔍 search by skill or interest…"
""",
"""          placeholder="Search by skill or interest…"
""", 1), (
"""                  {t.skills.map((s) => (
                    <span className="kw" key={`s-${s}`}>⚙ {s}</span>
                  ))}""",
"""                  {t.skills.map((s) => (
                    <span className="kw" key={`s-${s}`}><IconSliders size={12} /> {s}</span>
                  ))}""", 1), (
"""                  {t.interests.map((s) => (
                    <span className="kw kw-interest" key={`i-${s}`}>❤ {s}</span>
                  ))}""",
"""                  {t.interests.map((s) => (
                    <span className="kw kw-interest" key={`i-${s}`}><IconHeart size={12} /> {s}</span>
                  ))}""", 1), (
"""                    🏆 {t.experience}
""",
"""                    <IconAward size={14} /> {t.experience}
""", 1), (
"""                  {deleting === t.id ? '…' : '🗑'}
                </button>""",
"""                  {deleting === t.id ? '…' : <IconTrash size={15} />}
                </button>""", 1)])

# ---------------- Register.jsx ----------------
rep('pages/Register.jsx', [(
"import { Select } from '../components/ui.jsx'",
"import { Select } from '../components/ui.jsx'\nimport { IconInbox } from '../components/icons.jsx'", 1), (
"""          <div className="confirm-ico" aria-hidden="true">📬</div>""",
"""          <div className="confirm-ico" aria-hidden="true"><IconInbox size={40} /></div>""", 1)])

# ---------------- TeamMessages.jsx ----------------
rep('components/TeamMessages.jsx', [(
"toast.push('⚠️ Could not send message: ' + err.message)",
"toast.push('Could not send message: ' + err.message)", 1)])

if failures:
    print("FAILURES:")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print(f"OK — {applied} replacements applied")
