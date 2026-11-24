import { useEffect, useState } from 'react'
import { api } from '../api.js'
import CityMap from '../components/CityMap.jsx'
import { Empty, ErrorNote, Spinner } from '../components/ui.jsx'
import { IconAlert, IconCheck, IconClock, IconMapPin, IconRefresh } from '../components/icons.jsx'

export default function CityMapPage() {
  const [problems, setProblems] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    setError('')
    try {
      const data = await api('/api/problems/map/all')
      setProblems(data)
    } catch (err) {
      if (err.status !== 401) setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const total = problems?.length || 0
  const openCount = problems?.filter((p) => p.status === 'open').length || 0
  const assignedCount = problems?.filter((p) => p.status === 'assigned' || p.status === 'in_review').length || 0
  const resolvedCount = problems?.filter((p) => p.status === 'resolved').length || 0

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>City Incident Map</h1>
          <p className="page-sub">
            Real-time geospatial tracking of civic problems, AI student-team assignments, and resolved infrastructure.
          </p>
        </div>
        <button className="btn btn-outline" onClick={load} disabled={loading} title="Refresh map">
          <IconRefresh size={18} /> Refresh
        </button>
      </div>

      <ErrorNote>{error}</ErrorNote>

      <div className="mini-stats" style={{ marginBottom: 16 }}>
        <div className="mini-stat mine-blue">
          <span className="stat-icon" aria-hidden="true"><IconMapPin /></span>
          <div><b>{total}</b><span>Total Mapped</span></div>
        </div>
        <div className="mini-stat mine-green">
          <span className="stat-icon" aria-hidden="true"><IconClock /></span>
          <div><b>{openCount}</b><span>Open Issues</span></div>
        </div>
        <div className="mini-stat mine-amber">
          <span className="stat-icon" aria-hidden="true"><IconAlert /></span>
          <div><b>{assignedCount}</b><span>In Progress</span></div>
        </div>
        <div className="mini-stat mine-teal">
          <span className="stat-icon" aria-hidden="true"><IconCheck /></span>
          <div><b>{resolvedCount}</b><span>Resolved</span></div>
        </div>
      </div>

      {loading && !problems && <Spinner />}

      {problems && problems.length === 0 && (
        <Empty>No civic reports available to display on the map yet.</Empty>
      )}

      {problems && problems.length > 0 && (
        <CityMap problems={problems} height="620px" />
      )}
    </div>
  )
}
