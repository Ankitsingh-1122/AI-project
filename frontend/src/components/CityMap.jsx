import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Badge } from './ui.jsx'
import { IconMapPin, IconSliders, IconThumbsUp } from './icons.jsx'

// Fix standard Leaflet default marker icons in bundlers
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

const CATEGORY_COLORS = {
  water_supply: '#0284c7', // Sky Blue
  sewage: '#0369a1',       // Darker Blue
  pothole: '#d97706',      // Amber
  street_light: '#8b5cf6', // Violet
  garbage: '#10b981',      // Green
  default: '#ef4444',      // Red
}

function getMarkerColor(category = '') {
  const c = category.toLowerCase()
  if (c.includes('water')) return CATEGORY_COLORS.water_supply
  if (c.includes('sewage') || c.includes('drain')) return CATEGORY_COLORS.sewage
  if (c.includes('pothole') || c.includes('road')) return CATEGORY_COLORS.pothole
  if (c.includes('light') || c.includes('lamp')) return CATEGORY_COLORS.street_light
  if (c.includes('garbage') || c.includes('waste')) return CATEGORY_COLORS.garbage
  return CATEGORY_COLORS.default
}

function createCustomPin(color) {
  return L.divIcon({
    className: 'custom-map-pin',
    html: `
      <div style="
        background-color: ${color};
        width: 28px;
        height: 28px;
        border-radius: 50% 50% 50% 0;
        transform: rotate(-45deg);
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 10px rgba(0,0,0,0.35);
        border: 2px solid white;
        transition: transform 0.2s ease;
      ">
        <div style="
          width: 8px;
          height: 8px;
          background-color: white;
          border-radius: 50%;
        "></div>
      </div>
    `,
    iconSize: [28, 28],
    iconAnchor: [14, 28],
    popupAnchor: [0, -28],
  })
}

export default function CityMap({ problems = [], height = '560px' }) {
  const mapContainerRef = useRef(null)
  const mapInstanceRef = useRef(null)
  const markersLayerRef = useRef(null)
  const [filter, setFilter] = useState('all')

  const validProblems = problems.filter((p) => p.lat && p.lng)

  const filtered = validProblems.filter((p) => {
    if (filter === 'all') return true
    const c = (p.category || '').toLowerCase()
    if (filter === 'water') return c.includes('water') || c.includes('sewage')
    if (filter === 'road') return c.includes('pothole') || c.includes('road')
    if (filter === 'light') return c.includes('light') || c.includes('lamp')
    if (filter === 'waste') return c.includes('garbage') || c.includes('waste')
    return true
  })

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current) return

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: [30.9010, 75.8573], // Ludhiana Center
        zoom: 13,
        zoomControl: true,
      })

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map)

      markersLayerRef.current = L.layerGroup().addTo(map)
      mapInstanceRef.current = map

      // Force recalculation of container size after mounting
      setTimeout(() => {
        map.invalidateSize()
      }, 200)
    }

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove()
        mapInstanceRef.current = null
      }
    }
  }, [])

  // Render Markers on Map
  useEffect(() => {
    const map = mapInstanceRef.current
    const layer = markersLayerRef.current
    if (!map || !layer) return

    layer.clearLayers()

    const bounds = []

    filtered.forEach((p) => {
      const color = getMarkerColor(p.category)
      const pinIcon = createCustomPin(color)
      const marker = L.marker([p.lat, p.lng], { icon: pinIcon })

      bounds.push([p.lat, p.lng])

      const statusBadgeTone =
        p.status === 'resolved'
          ? 'green'
          : p.status === 'assigned'
            ? 'amber'
            : 'blue'

      const statusText =
        p.status === 'resolved'
          ? 'Resolved'
          : p.status === 'assigned'
            ? (p.assigned_team?.team_name ? `Assigned to ${p.assigned_team.team_name}` : 'Assigned')
            : 'Open'

      const popupHtml = `
        <div style="font-family: inherit; min-width: 210px; max-width: 280px; padding: 4px;">
          <div style="font-weight: 600; font-size: 0.95rem; line-height: 1.3; margin-bottom: 6px; color: #0f172a;">
            ${p.title}
          </div>
          <div style="display: flex; gap: 6px; margin-bottom: 8px; flex-wrap: wrap;">
            <span style="background: #e2e8f0; color: #334155; font-size: 0.72rem; padding: 2px 7px; border-radius: 9999px; font-weight: 500;">
              ${(p.category || 'general').replace(/_/g, ' ')}
            </span>
            <span style="background: ${statusBadgeTone === 'green' ? '#dcfce7' : statusBadgeTone === 'amber' ? '#fef3c7' : '#dbeafe'}; color: ${statusBadgeTone === 'green' ? '#166534' : statusBadgeTone === 'amber' ? '#92400e' : '#1e40af'}; font-size: 0.72rem; padding: 2px 7px; border-radius: 9999px; font-weight: 600;">
              ${statusText}
            </span>
          </div>
          <div style="font-size: 0.8rem; color: #64748b; margin-bottom: 10px;">
            📍 ${p.location || 'Ludhiana'}
            ${p.upvotes > 0 ? `<span style="margin-left: 8px;">👍 <b>${p.upvotes}</b> upvotes</span>` : ''}
          </div>
          <a href="/problem/${p.id}" style="
            display: block;
            text-align: center;
            background: #2563eb;
            color: white;
            font-size: 0.82rem;
            font-weight: 600;
            padding: 6px 10px;
            border-radius: 6px;
            text-decoration: none;
          ">View Full Report →</a>
        </div>
      `

      marker.bindPopup(popupHtml)
      layer.addLayer(marker)
    })

    if (bounds.length > 0) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 })
    }
  }, [filtered])

  return (
    <div className="city-map-wrapper card" style={{ padding: 16, overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <IconMapPin size={22} color="var(--primary, #2563eb)" />
          <span style={{ fontWeight: 600, fontSize: '1.05rem' }}>
            Interactive City GIS Map
          </span>
          <span className="badge badge-blue" style={{ fontSize: '0.75rem', padding: '2px 8px' }}>
            {filtered.length} reports mapped
          </span>
        </div>

        <div className="seg" role="group" aria-label="Map category filter">
          {[
            ['all', 'All'],
            ['water', 'Water / Sewage'],
            ['road', 'Roads & Potholes'],
            ['light', 'Street Lights'],
            ['waste', 'Garbage / Waste'],
          ].map(([val, label]) => (
            <button
              key={val}
              type="button"
              className={'seg-btn' + (filter === val ? ' active' : '')}
              onClick={() => setFilter(val)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div
        ref={mapContainerRef}
        style={{
          height,
          width: '100%',
          borderRadius: 10,
          boxShadow: 'inset 0 0 10px rgba(0,0,0,0.1)',
          zIndex: 1,
        }}
      />

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 12, fontSize: '0.8rem', color: 'var(--muted, #64748b)' }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: CATEGORY_COLORS.water_supply }}></span> Water / Drainage
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: CATEGORY_COLORS.pothole }}></span> Roads & Potholes
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: CATEGORY_COLORS.street_light }}></span> Street Lights
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: CATEGORY_COLORS.garbage }}></span> Sanitation & Waste
        </span>
      </div>
    </div>
  )
}
