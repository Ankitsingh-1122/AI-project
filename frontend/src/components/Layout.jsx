import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth.jsx'
import { useTheme } from '../theme.jsx'
import NotificationBell from './NotificationBell.jsx'
import { IconBack, IconChart, IconClipboard, IconEdit, IconFwd, IconHome, IconLogout, IconMoon, IconSun, IconTarget, IconUser, IconUsers } from './icons.jsx'


function initials(name = '') {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return '?'
  return (parts[0][0] + (parts[1]?.[0] || '')).toUpperCase()
}

/*
 * Browser-history aware Back/Forward built on react-router's navigate().
 * NOTE: the history index lives in window.history.state.idx — react-router
 * v6 keeps user state separately (location.state is the `usr` payload).
 */
function useBrowserNav() {
  const navigate = useNavigate()
  const location = useLocation()
  const [idx, setIdx] = useState(() => window.history.state?.idx ?? 0)
  useEffect(() => {
    setIdx(window.history.state?.idx ?? 0)
  }, [location.key])
  const maxIdx = useRef(window.history.state?.idx ?? 0)
  useEffect(() => {
    if (idx >= maxIdx.current) maxIdx.current = idx
  }, [idx])
  return {
    canBack: idx > 0,
    canFwd: idx < maxIdx.current,
    back: () => navigate(-1),
    fwd: () => navigate(1),
  }
}

function navGroupsFor(user) {
  const groups = []
  if (user.role === 'citizen' || user.role === 'admin') {
    groups.push({
      label: user.role === 'admin' ? 'Citizen' : '',
      items: [
        { to: '/dashboard', label: 'My Problems', icon: IconClipboard },
        { to: '/submit', label: 'Submit Problem', icon: IconEdit },
        // citizens can browse (but not edit) team profiles
        ...(user.role === 'citizen' ? [{ to: '/teams', label: 'Teams Directory', icon: IconUsers }] : []),
      ],
    })
  }
  if (user.role === 'team' || user.role === 'admin') {
    groups.push({
      label: user.role === 'admin' ? 'Team' : '',
      items: [
        { to: '/team', label: 'Team Home', icon: IconHome, end: true },
        { to: '/team/recommended', label: 'Recommended', icon: IconTarget },
        { to: '/teams', label: 'Teams Directory', icon: IconUsers },
      ],
    })
  }
  if (user.role === 'admin') {
    groups.push({
      label: 'Admin',
      items: [{ to: '/admin', label: 'Admin Dashboard', icon: IconChart }],
    })
  }
  groups.push({
    label: user.role === 'admin' ? 'Account' : '',
    items: [{ to: '/profile', label: 'My Profile', icon: IconUser, end: true }],
  })
  return groups
}

function ThemeButton() {
  const { theme, toggle } = useTheme()
  return (
    <button className="theme-btn" onClick={toggle} aria-label="Toggle light / dark mode" title="Toggle light / dark mode">
      <span className="theme-icon" aria-hidden="true">
        {theme === 'dark' ? <IconSun size={18} /> : <IconMoon size={18} />}
      </span>
    </button>
  )
}

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [drawer, setDrawer] = useState(false)
  const nav = useBrowserNav()

  useEffect(() => setDrawer(false), [location.pathname])

  useEffect(() => {
    document.body.style.overflow = drawer ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [drawer])

  useEffect(() => {
    if (!drawer) return
    const onKey = (e) => { if (e.key === 'Escape') setDrawer(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [drawer])

  async function onLogout() {
    await logout()
    setDrawer(false)
    navigate('/')
  }

  const groups = user ? navGroupsFor(user) : []
  const av = user ? initials(user.name) : '?'

  const sidebarInner = (
    <>
      <Link to={user ? '/' : '/'} className="sidebar-brand" onClick={() => setDrawer(false)}>
        <span className="brand-icon"><img src="/logo-mark.png" alt="" aria-hidden="true" /></span>
        <span className="brand-name">
          Civic<span className="grad">AI</span>
        </span>
      </Link>

      <nav className="side-nav">
        {groups.map((g, gi) => (
          <div className="nav-group" key={g.label || gi}>
            {g.label && <div className="nav-section">{g.label}</div>}
            {g.items.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.end}
                onClick={() => setDrawer(false)}
                className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}
              >
                <span className="nav-icon" aria-hidden="true">{l.icon ? <l.icon size={18} /> : null}</span>
                <span className="nav-label">{l.label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="sidebar-foot">
        {user && (
          <Link to="/profile" className="user-card" onClick={() => setDrawer(false)} title="View my profile">
            <span className="user-avatar">{av}</span>
            <span className="user-meta">
              <span className="user-name">{user.name}</span>
              <span className={'role role-' + user.role}>{user.role}</span>
            </span>
          </Link>
        )}
        {user && (
          <button className="btn btn-ghost btn-block" onClick={onLogout}>
            <IconLogout size={15} /> Log out
          </button>
        )}
      </div>
    </>
  )

  return (
    <div className="app-shell">
      <aside className={'sidebar' + (drawer ? ' open' : '')} aria-label="Main navigation">
        {sidebarInner}
      </aside>
      {drawer && <div className="drawer-overlay" onClick={() => setDrawer(false)} aria-hidden="true" />}

      <div className="main-col">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className={'hamburger' + (drawer ? ' active' : '')}
              aria-label={drawer ? 'Close menu' : 'Open menu'}
              aria-expanded={drawer}
              onClick={() => setDrawer((d) => !d)}
            >
              <span /><span /><span />
            </button>
            <div className="nav-btn-group">
              <button
                className="icon-btn"
                onClick={nav.back}
                disabled={!nav.canBack}
                aria-label="Go back"
                title="Back"
              >
                <IconBack />
              </button>
              <button
                className="icon-btn"
                onClick={nav.fwd}
                disabled={!nav.canFwd}
                aria-label="Go forward"
                title="Forward"
              >
                <IconFwd />
              </button>
            </div>
          </div>
          <Link to="/" className="topbar-brand">
            <span className="brand-icon"><img src="/logo-mark.png" alt="" aria-hidden="true" /></span>
            <span className="brand-text">
              Civic<span className="grad">AI</span>
            </span>
          </Link>
          <div className="topbar-spacer" />
          {user && (
            <Link to="/profile" className="user-chip" title="View my profile">
              <span className="chip-avatar">{av}</span>
              <span className="chip-name-wrap">
                <span className="user-name">{user.name}</span>{' '}
                <span className={'role role-' + user.role}>{user.role}</span>
              </span>
            </Link>
          )}
          <ThemeButton />
          <NotificationBell />
        </header>

        <main className="content" key={location.pathname}>
          <Outlet />
        </main>

        <footer className="footer">
          CivicAI · AI-powered citizen problem deduplication, clustering &amp; student-team matching
        </footer>
      </div>
    </div>
  )
}
