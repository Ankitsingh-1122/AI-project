import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth.jsx'
import NotificationBell from './NotificationBell.jsx'
import TextSize from './TextSize.jsx'
import { IconBack, IconChart, IconClipboard, IconEdit, IconHome, IconLogout, IconMenu, IconTarget, IconUser, IconUsers, IconX } from './icons.jsx'

function initials(name = '') {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return '?'
  return (parts[0][0] + (parts[1]?.[0] || '')).toUpperCase()
}

/* Pages people land on after logging in: no "Back" button needed there. */
const HOME_PATHS = ['/dashboard', '/team', '/admin']

/* Is there a previous page inside the app to go back to? */
function useCanGoBack() {
  const location = useLocation()
  const [idx, setIdx] = useState(() => window.history.state?.idx ?? 0)
  useEffect(() => {
    setIdx(window.history.state?.idx ?? 0)
  }, [location.key])
  return idx > 0
}

/* One simple menu per role, in plain words. Icon AND text on every item. */
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
  const [drawer, setDrawer] = useState(false)

  // New page: close the phone menu and start at the top.
  useEffect(() => {
    setDrawer(false)
    window.scrollTo(0, 0)
  }, [location.pathname])

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

  const items = user ? navItemsFor(user) : []
  const showBack = canBack && !HOME_PATHS.includes(location.pathname)

  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">Skip to main content</a>

      <aside className={'sidebar' + (drawer ? ' open' : '')} aria-label="Main menu">
        <div className="sidebar-top">
          <Link to="/" className="sidebar-brand" aria-label="CivicAI home">
            <span className="brand-icon"><img src="/logo-mark.png" alt="" aria-hidden="true" /></span>
            <span className="brand-name">Civic<span className="grad">AI</span></span>
          </Link>
          <button className="drawer-close" onClick={() => setDrawer(false)} aria-label="Close menu">
            <IconX size={22} />
          </button>
        </div>

        <nav className="side-nav">
          {items.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}
            >
              <span className="nav-icon" aria-hidden="true"><l.icon size={22} /></span>
              <span className="nav-label">{l.label}</span>
            </NavLink>
          ))}
        </nav>

        {user && (
          <div className="sidebar-foot">
            <Link to="/profile" className="user-card" title="My account">
              <span className="user-avatar" aria-hidden="true">{initials(user.name)}</span>
              <span className="user-meta">
                <span className="user-name">{user.name}</span>
                <span className={'role role-' + user.role}>{user.role}</span>
              </span>
            </Link>
            <button className="btn btn-outline btn-block" onClick={onLogout}>
              <IconLogout size={20} /> Log out
            </button>
          </div>
        )}
      </aside>
      {drawer && <div className="drawer-overlay" onClick={() => setDrawer(false)} aria-hidden="true" />}

      <div className="main-col">
        <header className="app-topbar">
          <button
            className="menu-btn"
            onClick={() => setDrawer(true)}
            aria-label="Open menu"
            aria-expanded={drawer}
          >
            <IconMenu size={24} /> <span>Menu</span>
          </button>
          <div className="topbar-spacer" />
          <TextSize />
          <NotificationBell />
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
    </div>
  )
}
