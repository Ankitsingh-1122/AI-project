import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth.jsx'
import NotificationBell from './NotificationBell.jsx'
import TextSize from './TextSize.jsx'
import { IconBack, IconChart, IconClipboard, IconEdit, IconHome, IconLogout, IconTarget, IconUser, IconUsers } from './icons.jsx'

function initials(name = '') {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return '?'
  return (parts[0][0] + (parts[1]?.[0] || '')).toUpperCase()
}

/* Pages people land on after logging in: no "Back" button needed there. */
const HOME_PATHS = ['/dashboard', '/team', '/admin']

/*
 * Is there a previous page inside the app to go back to?
 * (react-router v6 keeps its history index in window.history.state.idx.)
 */
function useCanGoBack() {
  const location = useLocation()
  const [idx, setIdx] = useState(() => window.history.state?.idx ?? 0)
  useEffect(() => {
    setIdx(window.history.state?.idx ?? 0)
  }, [location.key])
  return idx > 0
}

/*
 * One simple menu per role, in plain words. Every item has an icon AND a
 * text label — icons alone are easy to misread.
 */
function navItemsFor(user) {
  const items = []
  const isCitizen = user.role === 'citizen'
  const isTeam = user.role === 'team'
  const isAdmin = user.role === 'admin'

  if (isAdmin) items.push({ to: '/admin', label: 'Admin', icon: IconChart })
  if (isCitizen || isAdmin) {
    items.push({ to: '/dashboard', label: 'My Reports', icon: IconClipboard })
    items.push({ to: '/submit', label: 'Report a Problem', icon: IconEdit })
  }
  if (isTeam || isAdmin) {
    items.push({ to: '/team', label: 'My Team', icon: IconHome, end: true })
    items.push({ to: '/team/recommended', label: 'Suggested Problems', icon: IconTarget })
  }
  items.push({ to: '/teams', label: 'All Teams', icon: IconUsers })
  items.push({ to: '/profile', label: 'My Account', icon: IconUser, end: true })
  return items
}

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const canBack = useCanGoBack()

  // New page → start at the top.
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [location.pathname])

  async function onLogout() {
    await logout()
    navigate('/')
  }

  const items = user ? navItemsFor(user) : []
  const showBack = canBack && !HOME_PATHS.includes(location.pathname)

  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">Skip to main content</a>

      <header className="topbar">
        <div className="topbar-row">
          <Link to="/" className="topbar-brand" aria-label="CivicAI home">
            <span className="brand-icon"><img src="/logo-mark.png" alt="" aria-hidden="true" /></span>
            <span className="brand-text">
              Civic<span className="grad">AI</span>
            </span>
          </Link>

          <div className="topbar-spacer" />

          <TextSize />
          <NotificationBell />

          {user && (
            <>
              <Link to="/profile" className="user-chip" title="My account">
                <span className="chip-avatar" aria-hidden="true">{initials(user.name)}</span>
                <span className="chip-name-wrap">
                  <span className="user-name">{user.name}</span>
                </span>
              </Link>
              <button className="btn btn-outline logout-btn" onClick={onLogout}>
                <IconLogout size={18} />
                <span className="logout-text">Log out</span>
              </button>
            </>
          )}
        </div>

        {user && (
          <nav className="main-nav" aria-label="Main menu">
            {items.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.end}
                className={({ isActive }) => 'main-nav-item' + (isActive ? ' active' : '')}
              >
                <span className="main-nav-icon" aria-hidden="true"><l.icon size={22} /></span>
                <span className="main-nav-label">{l.label}</span>
              </NavLink>
            ))}
          </nav>
        )}
      </header>

      <main className="content" id="main" key={location.pathname}>
        {showBack && (
          <button className="back-btn" onClick={() => navigate(-1)}>
            <IconBack size={20} /> Back
          </button>
        )}
        <Outlet />
      </main>

      <footer className="footer">
        CivicAI · Report a problem in your area and we connect it with a team that can help.
      </footer>
    </div>
  )
}
