import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useToast } from '../toast.jsx'
import { Spinner } from './ui.jsx'

/*
 * Shared team message thread. A message sent to a team lands in ONE
 * conversation visible to the team's whole member list (they log in as the
 * team) and to whoever wrote it. Every message is persisted server-side,
 * and each side also gets a bell notification, so the record survives logouts.
 */

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.toLocaleDateString()} · ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
}

export default function TeamMessages({ teamId, teamName }) {
  const { user } = useAuth()
  const toast = useToast()
  const [messages, setMessages] = useState(null)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const listRef = useRef(null)

  const load = useCallback(() => {
    api(`/api/teams/${teamId}/messages`)
      .then(setMessages)
      .catch(() => {})
  }, [teamId])

  useEffect(() => {
    load()
  }, [load])

  // keep the newest message in view
  useEffect(() => {
    const el = listRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages?.length])

  async function send(e) {
    e?.preventDefault()
    const body = text.trim()
    if (!body) return
    setBusy(true)
    try {
      await api(`/api/teams/${teamId}/messages`, { method: 'POST', body: { body } })
      setText('')
      load()
      // let the notification bell refresh its badge right away
      window.dispatchEvent(new Event('civic-notifications'))
    } catch (err) {
      toast.push('⚠️ Could not send message: ' + err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!user) return null
  if (!messages)
    return (
      <div className="card">
        <Spinner label="Loading messages…" />
      </div>
    )

  return (
    <div className="card msg-card">
      <h3>
        Messages with {teamName}
        <span className="muted small"> · shared with every member of the team</span>
      </h3>
      <div className="msg-thread" ref={listRef}>
        {messages.length === 0 && (
          <div className="empty">No messages yet — start the conversation below.</div>
        )}
        {messages.map((m) => {
          const mine = m.sender_id != null && m.sender_id === user.id
          return (
            <div key={m.id} className={'msg-item' + (mine ? ' mine' : '')}>
              <div className="msg-bubble">{m.body}</div>
              <div className="msg-meta">
                {mine ? 'You' : m.sender_name} · {fmtTime(m.created_at)}
              </div>
            </div>
          )
        })}
      </div>
      <form className="msg-compose" onSubmit={send}>
        <textarea
          rows={2}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={`Message ${teamName} — visible to all team members`}
          maxLength={1000}
        />
        <button className="btn btn-primary btn-sm" disabled={busy || !text.trim()}>
          {busy ? 'Sending…' : 'Send message'}
        </button>
      </form>
    </div>
  )
}
