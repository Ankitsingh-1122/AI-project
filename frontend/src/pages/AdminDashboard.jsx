import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { IconAlert, IconBox, IconCheckCircle, IconClipboard, IconCpu, IconLayers, IconRefresh, IconUsers } from '../components/icons.jsx'
import { api, apiBlob } from '../api.js'
import { useTheme } from '../theme.jsx'
import { Badge, Empty, ErrorNote, Spinner, StatCard } from '../components/ui.jsx'
import DataLabels from '../components/DataLabels.jsx'

const CHART_KINDS = ['category', 'status', 'timeline', 'heatmap', 'cluster_scatter']
const CHART_TITLES = {
  category: 'Problems by category — Seaborn barplot (muted categorical palette)',
  status: 'Problems by status — Seaborn barplot (status hues & percentage shares)',
  timeline: 'Growth over time — Seaborn lineplot & density area',
  heatmap: 'Category × Status cross-tabulation matrix — Seaborn heatmap',
  cluster_scatter: 'AI Cluster Map — 2D PCA of problem embeddings (hue=cluster, style=category, palette=husl)'
}

export default function AdminDashboard() {
  const location = useLocation()
  const { theme } = useTheme()
  const [stats, setStats] = useState(null)
  const [perf, setPerf] = useState(null)
  const [clusters, setClusters] = useState(null)
  const [feedback, setFeedback] = useState(null)
  const [recent, setRecent] = useState(null)
  const [charts, setCharts] = useState({})
  const [chartErr, setChartErr] = useState('')
  const [error, setError] = useState('')
  const chartUrls = useRef({})

  // Deep links: /admin#clusters and /admin#model-performance scroll to
  // the matching section once the dashboard has rendered.
  useEffect(() => {
    if (!location.hash || !stats) return
    const el = document.getElementById(location.hash.slice(1))
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [location.hash, stats])

  // Seaborn / matplotlib charts are rendered server-side as transparent PNGs,
  // themed to the current light/dark mode, and fetched as blobs because
  // <img> tags cannot send auth headers.
  useEffect(() => {
    let live = true
    async function run() {
      try {
        const next = {}
        let anySuccess = false
        for (const kind of CHART_KINDS) {
          try {
            const blob = await apiBlob(`/api/admin/charts/${kind}?theme=${theme}`)
            if (!live) return
            next[kind] = URL.createObjectURL(blob)
            anySuccess = true
          } catch (e) {
            console.warn(`Chart ${kind} unavailable:`, e)
          }
        }
        const old = chartUrls.current
        chartUrls.current = next
        setCharts(next)
        if (!anySuccess) {
          setChartErr('Charts are rendering or backend is reloading...')
        } else {
          setChartErr('')
        }
        Object.values(old).forEach((u) => u && URL.revokeObjectURL(u))
      } catch (e) {
        if (live) setChartErr(e.message)
      }
    }
    run()
    return () => { live = false }
  }, [theme])

  useEffect(() => {
    const urls = chartUrls
    return () => {
      Object.values(urls.current).forEach((u) => u && URL.revokeObjectURL(u))
    }
  }, [])

  useEffect(() => {
    load()
  }, [])

  async function load() {
    try {
      const [s, p, c, f, r] = await Promise.all([
        api('/api/admin/statistics'),
        api('/api/admin/model-performance'),
        api('/api/ai/clusters'),
        api('/api/feedback'),
        api('/api/problems')
      ])
      setStats(s)
      setPerf(p)
      setClusters(c)
      setFeedback(f)
      setRecent(r.slice(0, 6))
    } catch (err) {
      setError(err.message)
    }
  }

  if (error && !stats) return <ErrorNote>{error}</ErrorNote>
  if (!stats) return <Spinner label="Computing statistics & AI evaluation…" />

  const dedup = perf?.duplicate_detection || {}
  const cm = dedup.confusion_matrix || {}
  const matching = perf?.team_matching || {}
  const clusterEval = perf?.clustering || {}

  return (
    <div>
      <div className="page-head">
        <h1>Admin dashboard</h1>
        <button className="btn btn-ghost btn-sm" onClick={load}><IconRefresh size={14} /> Refresh</button>
      </div>

      <ErrorNote>{error}</ErrorNote>

      <div className="stat-grid">
        <StatCard label="Total problems" value={stats.total_problems} tone="blue" icon={<IconClipboard />}
          to="/dashboard" title="Open the problems list" />
        <StatCard label="Unique problems" value={stats.unique_problems} tone="green" icon={<IconCheckCircle />}
          to="/dashboard?dup=unique" title="Show unique (non-duplicate) problems" />
        <StatCard label="Duplicate reports" value={stats.duplicate_reports}
          sub={stats.total_problems ? `${((stats.duplicate_reports / stats.total_problems) * 100).toFixed(0)}% of all reports` : ''}
          tone="red" icon={<IconAlert />}
          to="/dashboard?dup=duplicates" title="Show duplicate reports" />
        <StatCard label="Clusters" value={stats.clusters} tone="violet" icon={<IconLayers />}
          to="/admin#clusters" title="Jump to the clusters section below" />
        <StatCard label="Registered teams" value={stats.registered_teams} tone="amber" icon={<IconUsers />}
          to="/teams" title="Open the teams directory" />
        <StatCard label="AI recommendations" value={stats.total_recommendations}
          sub={`${stats.match_status?.accepted || 0} accepted · ${stats.match_status?.rejected || 0} rejected`}
          tone="teal" icon={<IconCpu />}
          to="/admin#model-performance" title="Jump to the AI/ML performance section" />
      </div>

      <div className="card">
        <h3>
          Analytics charts
          <span className="muted small"> · rendered server-side with seaborn + matplotlib from live data</span>
        </h3>
        {chartErr ? (
          <ErrorNote>{chartErr}</ErrorNote>
        ) : (
          <div className="chart-grid">
            {CHART_KINDS.map((kind) =>
              charts[kind] ? (
                <figure className="chart-fig" key={kind}>
                  <img src={charts[kind]} alt={CHART_TITLES[kind]} />
                  <figcaption className="muted small">{CHART_TITLES[kind]}</figcaption>
                </figure>
              ) : (
                <div className="chart-fig chart-loading" key={kind}>
                  <span className="spinner" /> rendering…
                </div>
              )
            )}
          </div>
        )}
      </div>

      {recent && (
        <div className="card">
          <h3>Recent activity <span className="muted small">· latest citizen reports</span></h3>
          {recent.length === 0 ? (
            <Empty>No problems yet.</Empty>
          ) : (
            recent.map((p) => (
              <div className="recent-row" key={p.id}>
                <span className={'recent-dot ' + p.status} title={p.status} />
                <Link to={`/problem/${p.id}`} className="recent-title">#{p.id} · {p.title}</Link>
                <Badge tone="blue">{p.category.replace(/_/g, ' ')}</Badge>
                <Badge tone={{ open: 'blue', in_review: 'amber', assigned: 'violet', resolved: 'green' }[p.status] || 'gray'}>
                  {p.status.replace(/_/g, ' ')}
                </Badge>
                {p.assigned_team && (
                  <Badge tone="green">Team: {p.assigned_team.team_name}</Badge>
                )}
                <span className="recent-meta">{new Date(p.created_at).toLocaleDateString()}</span>
              </div>
            ))
          )}
        </div>
      )}

      

      <div className="card" id="model-performance">
        <h3>
          AI/ML performance{' '}
          <span className="muted small">
            embedder: {perf?.embedder_in_use || '—'} · duplicate method: {dedup.method || '—'} · threshold: {dedup.threshold ?? '—'} (evaluated on {dedup.pairs_evaluated ?? 0} labelled pairs)
          </span>
        </h3>
        {dedup.error && (
          <div className="muted small" style={{ marginBottom: 12, padding: '10px 12px', background: 'var(--hover-bg)', borderRadius: 10 }}>
            No human-labelled evaluation pairs exist for the demo problems yet — nothing below is computed from invented labels.
            Real model metrics are trained and reported from the <b>Data &amp; Labels</b> section (human labels on real 311 data)
            and the <b>Trained models in service</b> card.
          </div>
        )}
        <div className="perf-grid">
          <div>
            <h4>Duplicate detection</h4>
            <div className="metric-row"><span>Method</span><b>{dedup.method || '—'}</b></div>
            <div className="metric-row"><span>Precision</span><b>{fmt(dedup.precision)}</b></div>
            <div className="metric-row"><span>Recall</span><b>{fmt(dedup.recall)}</b></div>
            <div className="metric-row"><span>F1 score</span><b>{fmt(dedup.f1_score)}</b></div>
            {dedup.roc_auc !== undefined && (
              <div className="metric-row"><span>ROC-AUC (live pairs)</span><b>{fmt(dedup.roc_auc)}</b></div>
            )}
            <div className="confusion">
              <div className="conf-cell tp" title="True positives"><b>{cm.TP ?? 0}</b> TP</div>
              <div className="conf-cell fp" title="False positives"><b>{cm.FP ?? 0}</b> FP</div>
              <div className="conf-cell fn" title="False negatives"><b>{cm.FN ?? 0}</b> FN</div>
              <div className="conf-cell tn" title="True negatives"><b>{cm.TN ?? 0}</b> TN</div>
            </div>
            {dedup.examples?.false_positives?.length > 0 && (
              <div className="muted small">
                FP examples: {dedup.examples.false_positives.map((e) => `#${e.a}↔#${e.b} (${e.score})`).join(', ')}
              </div>
            )}
            {dedup.examples?.false_negatives?.length > 0 && (
              <div className="muted small">
                FN examples: {dedup.examples.false_negatives.map((e) => `#${e.a}↔#${e.b} (${e.score})`).join(', ')}
              </div>
            )}
          </div>
          <div>
            <h4>Team matching (P@K / R@K)</h4>
            <div className="metric-row"><span>Method</span><b>{matching.method || '—'}</b></div>
            <div className="metric-row"><span>Precision @ 3</span><b>{fmt(matching.mean?.precision_at_3)}</b></div>
            <div className="metric-row"><span>Precision @ 5</span><b>{fmt(matching.mean?.precision_at_5)}</b></div>
            <div className="metric-row"><span>Recall @ 3</span><b>{fmt(matching.mean_recall?.recall_at_3)}</b></div>
            <div className="metric-row"><span>Recall @ 5</span><b>{fmt(matching.mean_recall?.recall_at_5)}</b></div>
            <h4 style={{ marginTop: 16 }}>Clustering</h4>
            <div className="metric-row"><span>Clusters (k)</span><b>{clusterEval.clusters ?? '—'}</b></div>
            <div className="metric-row"><span>Silhouette</span><b>{fmt(clusterEval.silhouette_score)}</b></div>
            <div className="metric-row"><span>Cluster purity</span><b>{fmt(clusterEval.purity)}</b></div>
          </div>
        </div>
      </div>

      {perf?.trained_models && (
        <div className="card">
          <h3>
            Trained models in service{' '}
            <span className="muted small">
              retrain: <code>{perf.trained_models.retrain}</code>
            </span>
          </h3>
          <div className="perf-grid">
            <div>
              <h4>Duplicate classifier</h4>
              <div className="metric-row"><span>Active</span><b>{perf.trained_models.dedup_classifier.active ? 'yes' : 'no (cosine fallback)'}</b></div>
              {perf.trained_models.dedup_classifier.active && (
                <>
                  <div className="metric-row"><span>Model</span><b>{perf.trained_models.dedup_classifier.model || '—'}</b></div>
                  <div className="metric-row"><span>Decision threshold</span><b>{fmt(perf.trained_models.dedup_classifier.threshold)}</b></div>
                  <div className="metric-row"><span>Test Precision (held-out)</span><b>{fmt(perf.trained_models.dedup_classifier.test_metrics?.precision)}</b></div>
                  <div className="metric-row"><span>Test Recall (held-out)</span><b>{fmt(perf.trained_models.dedup_classifier.test_metrics?.recall)}</b></div>
                  <div className="metric-row"><span>Test F1 (held-out)</span><b>{fmt(perf.trained_models.dedup_classifier.test_metrics?.f1)}</b></div>
                  <div className="metric-row"><span>Test ROC-AUC (held-out)</span><b>{fmt(perf.trained_models.dedup_classifier.test_metrics?.roc_auc)}</b></div>
                </>
              )}
            </div>
            <div>
              <h4>Team-matching ranker</h4>
              <div className="metric-row"><span>Active</span><b>{perf.trained_models.team_ranker.active ? 'yes' : 'no (weighted formula)'}</b></div>
              {perf.trained_models.team_ranker.active && (
                <>
                  <div className="metric-row"><span>Model</span><b>{perf.trained_models.team_ranker.model || '—'}</b></div>
                  <div className="metric-row"><span>Precision @ 3 (held-out)</span><b>{fmt(perf.trained_models.team_ranker.test_metrics?.precision_at?.['3'] ?? perf.trained_models.team_ranker.test_metrics?.precision_at?.[3])}</b></div>
                  <div className="metric-row"><span>Precision @ 5 (held-out)</span><b>{fmt(perf.trained_models.team_ranker.test_metrics?.precision_at?.['5'] ?? perf.trained_models.team_ranker.test_metrics?.precision_at?.[5])}</b></div>
                  <div className="metric-row"><span>Recall @ 3 (held-out)</span><b>{fmt(perf.trained_models.team_ranker.test_metrics?.recall_at?.['3'] ?? perf.trained_models.team_ranker.test_metrics?.recall_at?.[3])}</b></div>
                  <div className="metric-row"><span>Test ROC-AUC</span><b>{fmt(perf.trained_models.team_ranker.val_auc || perf.trained_models.team_ranker.test_metrics?.auc)}</b></div>
                </>
              )}
              <h4 style={{ marginTop: 16 }}>Clustering selection</h4>
              <div className="metric-row"><span>Method (measured ARI)</span><b>{perf.trained_models.clustering.selected || '—'}</b></div>
              {perf.trained_models.clustering.selected === 'kmeans' && (
                <div className="metric-row"><span>k</span><b>{perf.trained_models.clustering.kmeans_k ?? '—'}</b></div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="two-col">
        <div className="card" id="clusters">
          <h3>Problem clusters (K-Means)</h3>
          {clusters?.length === 0 ? (
            <Empty>No clusters yet.</Empty>
          ) : (
            clusters?.map((c) => (
              <details className="cluster" key={c.id} open={c.size <= 8}>
                <summary>
                  <b><IconBox size={15} aria-hidden="true" /> {c.name}</b>
                  <Badge tone="violet">{c.size} problems</Badge>
                </summary>
                <ul className="cluster-members">
                  {c.members.map((m) => (
                    <li key={m.id}>
                      <Link to={`/problem/${m.id}`}>#{m.id} {m.title}</Link>
                      <span className="muted small"> · {m.category} · {m.status}</span>
                    </li>
                  ))}
                </ul>
              </details>
            ))
          )}
        </div>

        <div className="card">
          <h3>User feedback on AI decisions</h3>
          {feedback?.length === 0 ? (
            <Empty>No feedback yet.</Empty>
          ) : (
            feedback?.slice(0, 12).map((f) => (
              <div className="fb-item" key={f.id}>
                <div className="fb-head">
                  <Badge tone={f.feedback_type === 'good_match' || f.feedback_type === 'correct_duplicate' ? 'green' : f.feedback_type === 'bad_match' || f.feedback_type === 'wrong_duplicate' ? 'red' : 'gray'}>
                    {f.feedback_type}
                  </Badge>
                  <span className="muted small">{f.user}</span>
                </div>
                {f.match && (
                  <div className="muted small">
                    match: {f.match.problem_title} → {f.match.team_name}
                  </div>
                )}
                {f.comment && <p className="small">{f.comment}</p>}
              </div>
            ))
              )}
        </div>
      </div>

      <DataLabels />
    </div>
  )
}

function fmt(v) {
  if (v === null || v === undefined) return '—'
  return (typeof v === 'number' ? v : Number(v)).toFixed(2)
}
