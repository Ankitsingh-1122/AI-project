import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { Badge, Empty, Spinner } from './ui.jsx'
import { useToast } from '../toast.jsx'

const SOURCE_LABEL = {
  dup_flag: 'city-flagged',
  same_address: 'same address',
  negative: 'same type, different street',
}

function Progress({ have, need }) {
  const pct = Math.min(100, Math.round((have / Math.max(need, 1)) * 100))
  return (
    <div style={{ flex: 1, minWidth: 120 }}>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: pct + '%' }} />
      </div>
    </div>
  )
}

export default function DataLabels({ refreshKey = 0 }) {
  const toast = useToast()
  const [status, setStatus] = useState(null)
  const [pairs, setPairs] = useState(null)
  const [rel, setRel] = useState(null)
  const [relView, setRelView] = useState('pending')
  const [busy, setBusy] = useState('')
  const [trainRes, setTrainRes] = useState(null)
  const [err, setErr] = useState('')
  const [pairOffset, setPairOffset] = useState(0)
  const [relOffset, setRelOffset] = useState(0)

  const loadStatus = useCallback(async () => {
    try {
      setStatus(await api('/api/labels/status'))
    } catch (e) {
      setErr(e.message)
    }
  }, [])

  const loadPairs = useCallback(async (offset = 0) => {
    try {
      setPairs(await api(`/api/labels/pairs?limit=5&offset=${offset}`))
    } catch (e) {
      setErr(e.message)
    }
  }, [])

  const loadRel = useCallback(async (view, offset = 0) => {
    try {
      setRel(await api(`/api/labels/relevance?status=${view}&limit=3&offset=${offset}`))
    } catch (e) {
      setErr(e.message)
    }
  }, [])

  useEffect(() => {
    loadStatus()
    loadPairs(0)
    loadRel('pending', 0)
  }, [loadStatus, loadPairs, loadRel, refreshKey])

  async function labelPair(pair, isDuplicate) {
    const prev = pairs
    setPairs({ ...pairs, total: pairs.total - 1, pairs: pairs.pairs.filter((x) => x.id !== pair.id) })
    try {
      await api(`/api/labels/pairs/${pair.id}`, { method: 'POST', body: { is_duplicate: isDuplicate } })
      toast.push(isDuplicate ? '✓ Marked as duplicate' : '✓ Marked as not a duplicate')
      loadStatus()
      if (pairOffset > 0 && (pairs.pairs.length - 1) <= 0) {
        setPairOffset(pairOffset - 5)
        loadPairs(pairOffset - 5)
      }
    } catch (e) {
      setPairs(prev)
      toast.push(e.message, 'error')
    }
  }

  async function toggleRelevant(problemId, teamId, relevant) {
    setRel((r) => r && {
      ...r,
      items: r.items.map((it) => it.problem.id === problemId ? {
        ...it,
        teams: it.teams.map((t) => t.team_id === teamId ? { ...t, relevant } : t),
      } : it),
    })
    try {
      await api('/api/labels/relevance', { method: 'POST', body: { problem_id: problemId, team_id: teamId, relevant } })
      loadStatus()
    } catch (e) {
      toast.push(e.message, 'error')
      loadRel(relView, relOffset)
    }
  }

  async function mine() {
    setBusy('mine')
    try {
      const r = await api('/api/labels/mine', { method: 'POST', body: { pairs: 300, relevance_problems: 60 } })
      toast.push(`Mining done: +${r.problems_added} problems, pairs +${(r.pairs_mined?.dup_flag ?? 0)}/${(r.pairs_mined?.same_address ?? 0)}/${(r.pairs_mined?.negative ?? 0)}`)
      setPairOffset(0)
      setRelOffset(0)
      loadStatus()
      loadPairs(0)
      loadRel('pending', 0)
    } catch (e) {
      toast.push(e.message, 'error')
    } finally {
      setBusy('')
    }
  }

  async function train() {
    setBusy('train')
    setTrainRes(null)
    try {
      const r = await api('/api/labels/retrain', { method: 'POST', body: {} })
      setTrainRes(r)
      loadStatus()
    } catch (e) {
      setTrainRes({ error: e.message })
    } finally {
      setBusy('')
    }
  }

  if (!status && !err) return <Spinner label="Loading labelling status…" />

  const min = status?.minima_for_training || { dedup_pairs: 150, relevance_rows: 100 }
  const pp = status?.pairs || {}
  const relS = status?.relevance || {}
  const ready = status?.ready_to_train || {}
  const trained = status?.trained_models || {}

  return (
    <div className="card" id="data-labels">
      <div className="card-top">
        <div>
          <h3>Data &amp; Labels <Badge tone="teal">real Chicago/NYC 311</Badge></h3>
          <p className="muted small" style={{ marginTop: 4, marginBottom: 0 }}>
            Model training data is real civic open data (no synthetic records). Every label below is
            entered by a human — nothing is auto-generated. Progress toward the training minimums:
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button className="btn btn-outline btn-sm" disabled={!!busy} onClick={mine}>
            {busy === 'mine' ? 'Mining…' : '＋ Mine more candidates'}
          </button>
          <button className="btn btn-primary btn-sm" disabled={!!busy} onClick={train}>
            {busy === 'train' ? 'Training…' : '▶ Train models now'}
          </button>
        </div>
      </div>

      <div className="two-col" style={{ marginTop: 16 }}>
        <div>
          <div className="metric-row">
            <span>Duplicate pairs labelled</span>
            <b>{pp.total_labeled ?? 0} / {min.dedup_pairs}</b>
            <Progress have={pp.total_labeled ?? 0} need={min.dedup_pairs} />
          </div>
          <div className="metric-row">
            <span>Relevance rows labelled</span>
            <b>{relS.labeled_rows ?? 0} / {min.relevance_rows}</b>
            <Progress have={relS.labeled_rows ?? 0} need={min.relevance_rows} />
          </div>
          <div className="metric-row"><span>Real requests in DB</span><b>{status?.real_corpus_rows ?? '—'}</b></div>
          <div className="metric-row"><span>Relevance problems sampled</span><b>{relS.problems_sampled ?? '—'}</b></div>
          <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
            <Badge tone={ready.dedup ? 'green' : 'gray'}>
              dedup model: {trained.dedup_classifier ? 'trained' : ready.dedup ? 'ready to train' : 'awaiting labels'}
            </Badge>
            <Badge tone={ready.relevance ? 'green' : 'gray'}>
              ranker: {trained.team_ranker ? 'trained' : ready.relevance ? 'ready to train' : 'awaiting labels'}
            </Badge>
          </div>
          {trainRes && (
            <div className="muted small" style={{ marginTop: 10 }}>
              {trainRes.error
                ? <>Last training attempt failed: {trainRes.error}</>
                : <>
                    Last training: dedup {trainRes.dedup?.trained ? `trained in ${trainRes.dedup?.seconds}s` : trainRes.dedup?.reason || '—'}
                    {' · '}ranker {trainRes.relevance?.trained ? `trained in ${trainRes.relevance?.seconds}s` : trainRes.relevance?.reason || '—'}
                  </>}
            </div>
          )}
        </div>
        <div className="muted small">
          <b>How it works</b>
          <ol style={{ margin: '8px 0 0', paddingLeft: 18, lineHeight: 1.7 }}>
            <li>Mark each pair <b>duplicate</b> / <b>not a duplicate</b> (minimum {min.dedup_pairs}).</li>
            <li>Mark which student teams are relevant to each real problem (minimum {min.relevance_rows} rows).</li>
            <li>Press <b>Train models now</b> — the classifier &amp; ranker are trained on these labels only, with a leak-free split, and real held-out metrics appear in “AI/ML performance”.</li>
          </ol>
        </div>
      </div>

      <h4 style={{ marginTop: 20 }}>Duplicate review queue <span className="muted small">({pairs?.total ?? 0} pending)</span></h4>
      {!pairs ? <Spinner label="Loading pairs…" /> : pairs.pairs.length === 0 ? (
        <Empty>No pending pairs — press “Mine more candidates” to mine another batch.</Empty>
      ) : (
        <div className="card-list">
          {pairs.pairs.map((p) => (
            <div key={p.id} className="card" style={{ padding: 14 }}>
              <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap' }}>
                <div style={{ flex: 1, minWidth: 260 }}>
                  <div style={{ display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap' }}>
                    <Badge tone="blue">{SOURCE_LABEL[p.source] || p.source}</Badge>
                    <Badge tone="gray">{p.a?.source === 'chicago' ? 'Chicago 311' : 'NYC 311'}</Badge>
                    {p.a?.duplicate_flag === 1 && <Badge tone="amber">city flagged duplicate</Badge>}
                    {p.similarity != null && <Badge tone="gray">sim {p.similarity.toFixed(3)}</Badge>}
                  </div>
                  <div style={{ fontSize: 14, lineHeight: 1.55 }}>
                    <div><b>A.</b> {p.a?.text} <span className="muted">· {p.a?.location} · {p.a?.date}</span></div>
                    <div style={{ marginTop: 4 }}><b>B.</b> {p.b?.text} <span className="muted">· {p.b?.location} · {p.b?.date}</span></div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                  <button className="btn btn-primary btn-sm" onClick={() => labelPair(p, true)}>✓ Duplicate</button>
                  <button className="btn btn-outline btn-sm" onClick={() => labelPair(p, false)}>✗ Not a duplicate</button>
                </div>
              </div>
            </div>
          ))}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
            <button className="btn btn-ghost btn-sm" disabled={pairOffset === 0}
              onClick={() => { setPairOffset(pairOffset - 5); loadPairs(pairOffset - 5) }}>← Prev</button>
            <span className="muted small" style={{ alignSelf: 'center' }}>
              {Math.min(pairOffset + 5, pairs.total)} of {pairs.total}
            </span>
            <button className="btn btn-ghost btn-sm" disabled={pairOffset + 5 >= pairs.total}
              onClick={() => { setPairOffset(pairOffset + 5); loadPairs(pairOffset + 5) }}>Next →</button>
          </div>
        </div>
      )}

      <h4 style={{ marginTop: 20 }}>
        Team-relevance labelling
        <select value={relView} onChange={(e) => { setRelView(e.target.value); setRelOffset(0); loadRel(e.target.value, 0) }}
          style={{ marginLeft: 10, fontSize: 13 }}>
          <option value="pending">pending</option>
          <option value="labeled">labelled</option>
          <option value="all">all</option>
        </select>
      </h4>
      {!rel ? <Spinner label="Loading relevance grid…" /> : rel.items.length === 0 ? (
        <Empty>No problems in this view — mine more or switch the filter.</Empty>
      ) : (
        <div className="card-list">
          {rel.items.map((it) => (
            <div key={it.problem.id} className="card" style={{ padding: 14 }}>
              <div style={{ fontSize: 14, lineHeight: 1.55, marginBottom: 10 }}>
                <Badge tone="blue" style={{ marginRight: 6 }}>{it.problem.category.replace(/_/g, ' ')}</Badge>
                {it.problem.text} <span className="muted">· {it.problem.location} · {it.problem.date}</span>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {it.teams.map((t) => (
                  <button key={t.team_id}
                    className={'btn btn-sm ' + (t.relevant === 1 ? 'btn-primary' : t.relevant === 0 ? 'btn-outline' : 'btn-ghost')}
                    onClick={() => toggleRelevant(it.problem.id, t.team_id, t.relevant === 1 ? 0 : 1)}
                    title={t.relevant == null ? 'Click to mark relevant / not relevant' : 'Click to toggle'}>
                    {t.relevant === 1 ? '✓ ' : t.relevant === 0 ? '✗ ' : '· '}
                    {t.team_name}
                  </button>
                ))}
              </div>
            </div>
          ))}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
            <button className="btn btn-ghost btn-sm" disabled={relOffset === 0}
              onClick={() => { setRelOffset(relOffset - 3); loadRel(relView, relOffset - 3) }}>← Prev</button>
            <span className="muted small" style={{ alignSelf: 'center' }}>
              page {Math.floor(relOffset / 3) + 1}
            </span>
            <button className="btn btn-ghost btn-sm" disabled={rel.items.length < 3}
              onClick={() => { setRelOffset(relOffset + 3); loadRel(relView, relOffset + 3) }}>Next →</button>
          </div>
        </div>
      )}
    </div>
  )
}
