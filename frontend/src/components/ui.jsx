import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { IconAlert, IconMapPin } from './icons.jsx'
import { Link } from 'react-router-dom'

/*
 * Custom themed dropdown — native <select> popups ignore the app's dark
 * theme in some browsers (white popup + light text = invisible options),
 * so filters/status pickers use this fully-styled component instead.
 */
export function Select({ value, onChange, options, className = '', placeholder = 'Select…' }) {
  const [open, setOpen] = useState(false)
  const [menu, setMenu] = useState(null) // viewport coordinates (fixed positioning)
  const wrapRef = useRef(null)

  const norm = options.map((o) =>
    typeof o === 'string' ? { value: o, label: o } : o
  )
  const current = norm.find((o) => o.value === value)

  function close() {
    setOpen(false)
    setMenu(null)
  }

  function toggle() {
    if (open) {
      close()
      return
    }
    const btn = wrapRef.current?.querySelector('.select-btn')
    if (!btn) return
    const r = btn.getBoundingClientRect()
    const estH = Math.min(280, norm.length * 39 + 14)
    const width = Math.max(r.width, 190)
    const left = Math.max(8, Math.min(r.left, window.innerWidth - width - 8))
    const down = r.bottom + estH + 10 <= window.innerHeight
    const top = down ? r.bottom + 6 : Math.max(8, r.top - estH - 6)
    setMenu({ top, left, width })
    setOpen(true)
  }

  useEffect(() => {
    if (!open) return
    function onDown(e) {
      if (wrapRef.current?.contains(e.target)) return
      if (e.target.closest && e.target.closest('.select-menu')) return
      close()
    }
    function onKey(e) {
      if (e.key === 'Escape') close()
    }
    // close on scroll: fixed positioning would drift otherwise
    function onScroll() {
      close()
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    window.addEventListener('scroll', onScroll, true)
    window.addEventListener('resize', onScroll)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
      window.removeEventListener('scroll', onScroll, true)
      window.removeEventListener('resize', onScroll)
    }
  }, [open])

  return (
    <>
      <div className={'select-wrap' + (open ? ' open' : '') + (className ? ' ' + className : '')} ref={wrapRef}>
        <button
          type="button"
          className="select-btn"
          onClick={toggle}
          aria-haspopup="listbox"
          aria-expanded={open}
        >
          <span className={current ? 'select-value' : 'select-value muted'}>
            {current ? current.label : placeholder}
          </span>
          <svg className="select-chev" viewBox="0 0 24 24" aria-hidden="true">
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>
      </div>
      {open && menu &&
        createPortal(
          <ul
            className="select-menu"
            role="listbox"
            style={{ top: menu.top, left: menu.left, minWidth: menu.width }}
          >
            {norm.map((o) => (
              <li
                key={o.value}
                role="option"
                aria-selected={o.value === value}
                className={o.value === value ? 'selected' : ''}
                onClick={() => {
                  onChange(o.value)
                  close()
                }}
              >
                {o.label}
              </li>
            ))}
          </ul>,
          document.body
        )}
    </>
  )
}

export function StatCard({ label, value, sub, tone = 'blue', icon, to, title }) {
  const inner = (
    <>
      <div className="stat-head">
        <span>
          <span className="stat-value">{value}</span>
          <span className="stat-label">{label}</span>
        </span>
        {icon && <span className="stat-icon">{icon}</span>}
      </div>
      {sub && <span className="stat-sub">{sub}</span>}
      {to && <span className="stat-cta" aria-hidden="true">View →</span>}
    </>
  )
  if (!to) {
    return <div className={'stat-card tone-' + tone}>{inner}</div>
  }
  return (
    <Link to={to} className={'stat-card tone-' + tone + ' clickable'} title={title || `Open ${label.toLowerCase()}`}>
      {inner}
    </Link>
  )
}

export function Badge({ tone = 'gray', className = '', children }) {
  return <span className={('badge badge-' + tone + ' ' + className).trim()}>{children}</span>
}

export function statusTone(status) {
  return {
    open: 'blue',
    in_review: 'amber',
    assigned: 'violet',
    resolved: 'green',
  }[status] || 'gray'
}

export function DuplicateBadge({ p }) {
  if (p.is_duplicate) {
    const pct = p.duplicate_score != null ? Math.round(p.duplicate_score * 100) : null
    return (
      <span className="badge badge-red" title="Flagged as a probable duplicate by the trained classifier">
        <IconAlert size={13} /> Duplicate{pct != null ? ` · ${pct}%` : ''}
      </span>
    )
  }
  if (p.duplicate_score != null && p.duplicate_score > 0) {
    return (
      <span className="badge badge-gray" title="Top similarity score vs existing problems (not flagged)">
        ≈ {Math.round(p.duplicate_score * 100)}% similar
      </span>
    )
  }
  return null
}

export function ScoreBar({ value, score, label }) {
  const pct = Math.round(((score ?? value) || 0) * 100)
  return (
    <div className="scorebar" title={`${pct}%`}>
      <div className="scorebar-fill" style={{ width: pct + '%' }} />
      {label != null && <span className="scorebar-label">{pct}%</span>}
    </div>
  )
}

/*
 * "View Live Location" — the problem's `location` is a free-text field
 * (e.g. "Model Town, Ludhiana"). This opens it in a real map application
 * (Google Maps search) so the citizen sees the actual place. Rendered only
 * when a location exists — never a fake button.
 */
export function LocationButton({ location, small = false, label = 'View Live Location' }) {
  if (!location) return null
  const q = encodeURIComponent(location)
  const url = `https://www.google.com/maps/search/?api=1&query=${q}`
  const cls = small ? 'loc-btn loc-btn-sm' : 'loc-btn'
  return (
    <a className={cls} href={url} target="_blank" rel="noreferrer noopener" title={`Open “${location}” in Google Maps`}>
      <span className="loc-pin" aria-hidden="true"><IconMapPin size={15} /></span>
      {label}
    </a>
  )
}

export function Spinner({ label }) {
  return (
    <span>
      <span className="spinner" aria-label="Loading" />
      {label || ''}
    </span>
  )
}

export function ErrorNote({ msg, children }) {
  const text = msg ?? children
  return text ? <div className="note note-error">{text}</div> : null
}

export function Empty({ children }) {
  return <div className="empty">{children || 'Nothing here yet.'}</div>
}
