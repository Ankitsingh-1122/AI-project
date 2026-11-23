import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { IconAlert, IconBell, IconBellOff, IconCheck, IconCpu, IconLink, IconLogout, IconMessage } from './icons.jsx'

/*
 * Notification bell (top-right, after the light/dark toggle).
 * Every app event worth remembering — team messages, accept/reject
 * decisions, team removal — is stored server-side in the notifications
 * table, so this panel keeps a persistent, readable record for the user.
 */

const TYPE_META = {
  message: { icon: IconMessage, label: 'Message' },
  team_deleted: { icon: IconLogout, label: 'Team update' },
  match_decision: { icon: IconLink, label: 'Decision' },
  ai_auto_assignment: { icon: IconCpu, label: 'AI Auto-Assignment' },
  problem_assigned: { icon: IconLink, label: 'Assignment' },
  team_accepted: { icon: IconCheck, label: 'Team Accepted' },
  team_rejected: { icon: IconAlert, label: 'Team Declined' },
}

function timeAgo(iso) {
  if (!iso) return ''
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  if (s < 86400 * 7) return `${Math.floor(s / 86400)}d ago`
  return new Date(iso).toLocaleDateString()
}

export default function NotificationBell() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState(null)
  const [unread, setUnread] = useState(0)
  const [pos, setPos] = useState(null)
  const btnRef = useRef(null)

  const loadCount = useCallback(async () => {
    try {
      const r = await api('/api/notifications/unread-count')
      setUnread(r.count)
    } catch {
      /* offline / 401 handled elsewhere */
    }
  }, [])

  // Poll the unread badge while the app is open; also refresh when other
  // parts of the app (e.g. sending a team message) fire 'civic-notifications'.
  useEffect(() => {
    if (!user) return
    loadCount()
    const iv = setInterval(loadCount, 60000)
    const onManual = () => loadCount()
    window.addEventListener('civic-notifications', onManual)
    return () => {
      clearInterval(iv)
      window.removeEventListener('civic-notifications', onManual)
    }
  }, [user, loadCount])

  async function toggle() {
    if (open) {
      setOpen(false)
      setPos(null)
      return
    }
    const r = btnRef.current?.getBoundingClientRect()
    if (r) {
      const W = Math.min(400, window.innerWidth - 16)
      const H = 470
      const left = Math.max(8, Math.min(r.right - W, window.innerWidth - W - 8))
      const down = r.bottom + H + 12 <= window.innerHeight
      setPos({ left, top: down ? r.bottom + 8 : Math.max(8, r.top - 8) })
    }
    setOpen(true)
    try {
      const [list, count] = await Promise.all([
        api('/api/notifications'),
        api('/api/notifications/unread-count')
      ])
      setItems(list)
      setUnread(count.count)
    } catch {
      setItems([])
    }
  }

  async function markRead(id) {
    try {
      await api(`/api/notifications/${id}/read`, { method: 'POST' })
      setItems((xs) => xs && xs.map((x) => (x.id === id ? { ...x, is_read: true } : x)))
      setUnread((u) => Math.max(0, u - 1))
    } catch {
      /* non-fatal */
    }
  }

  async function markAll() {
    try {
      await api('/api/notifications/read-all', { method: 'POST' })
      setItems((xs) => xs && xs.map((x) => ({ ...x, is_read: true })))
      setUnread(0)
    } catch {
      /* non-fatal */
    }
  }

  // Close on outside click / Escape / scroll / resize (fixed positioning).
  useEffect(() => {
    if (!open) return
    function close() {
      setOpen(false)
      setPos(null)
    }
    function onDown(e) {
      if (btnRef.current?.contains(e.target)) return
      if (e.target.closest && e.target.closest('.notif-panel')) return
      close()
    }
    function onKey(e) {
      if (e.key === 'Escape') close()
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    window.addEventListener('scroll', onDown, true)
    window.addEventListener('resize', onDown)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
      window.removeEventListener('scroll', onDown, true)
      window.removeEventListener('resize', onDown)
    }
  }, [open])

  if (!user) return null

  return (
    <>
      <button
        ref={btnRef}
        className="theme-btn notif-bell"
        onClick={toggle}
        aria-label="Notifications"
        title="Notifications"
        aria-haspopup="true"
        aria-expanded={open}
      >
        <span className="notif-bell-icon" aria-hidden="true"><IconBell size={18} /></span>
        {unread > 0 && <span className="notif-badge">{unread > 9 ? '9+' : unread}</span>}
      </button>

      {open && pos &&
        createPortal(
          <div className="notif-panel" style={{ top: pos.top, left: pos.left }}>
            <div className="notif-head">
              <b>Notifications</b>
              {unread > 0 && (
                <button className="notif-markall" onClick={markAll}>
                  <IconCheck size={13} /> Mark all read
                </button>
              )}
            </div>
            <div className="notif-list">
              {items === null && <div className="notif-empty">Loading…</div>}
              {items?.length === 0 && (
                <div className="notif-empty"><IconBellOff size={16} /> You&apos;re all caught up.</div>
              )}
              {items?.map((n) => {
                const meta = TYPE_META[n.type] || { icon: IconBell, label: 'Notice' }
                return (
                  <div
                    key={n.id}
                    className={'notif-item' + (n.is_read ? '' : ' unread')}
                    onClick={() => !n.is_read && markRead(n.id)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => e.key === 'Enter' && !n.is_read && markRead(n.id)}
                  >
                    <span className="notif-ico" aria-hidden="true"><meta.icon size={16} /></span>
                    <span className="notif-body">
                      <span className="notif-title">
                        {n.title}
                        {!n.is_read && <span className="notif-dot" aria-label="unread" />}
                      </span>
                      {n.body && <span className="notif-text">{n.body}</span>}
                      <span className="notif-time">
                        {meta.label} · {timeAgo(n.created_at)}
                      </span>
                    </span>
                  </div>
                )
              })}
            </div>
          </div>,
          document.body
        )}
    </>
  )
}
