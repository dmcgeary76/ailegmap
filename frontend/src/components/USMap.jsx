import { useMemo, useState } from 'react'
import { geoAlbersUsa, geoPath } from 'd3-geo'
import { feature } from 'topojson-client'
import statesTopo from 'us-atlas/states-10m.json'
import './USMap.css'
import {
  stateColor, stanceKey, STAGE_COLORS, STAGE_LABELS, STANCE_COLORS, STANCE_LABELS,
  LEANING_COLORS, LEANING_LABELS, ACTION_LABELS,
} from '../api'

// Real geography: us-atlas TopoJSON (Census cartographic boundaries) projected
// with Albers USA, which places Alaska and Hawaii as insets automatically.
// DC and the territories are too small / off-projection, so they get boxes.

const FIPS = {
  '01': 'AL', '02': 'AK', '04': 'AZ', '05': 'AR', '06': 'CA', '08': 'CO', '09': 'CT', '10': 'DE',
  '11': 'DC', '12': 'FL', '13': 'GA', '15': 'HI', '16': 'ID', '17': 'IL', '18': 'IN', '19': 'IA',
  '20': 'KS', '21': 'KY', '22': 'LA', '23': 'ME', '24': 'MD', '25': 'MA', '26': 'MI', '27': 'MN',
  '28': 'MS', '29': 'MO', '30': 'MT', '31': 'NE', '32': 'NV', '33': 'NH', '34': 'NJ', '35': 'NM',
  '36': 'NY', '37': 'NC', '38': 'ND', '39': 'OH', '40': 'OK', '41': 'OR', '42': 'PA', '44': 'RI',
  '45': 'SC', '46': 'SD', '47': 'TN', '48': 'TX', '49': 'UT', '50': 'VT', '51': 'VA', '53': 'WA',
  '54': 'WV', '55': 'WI', '56': 'WY',
}

const W = 1000, H = 615
const projection = geoAlbersUsa().scale(1300).translate([487, 305])
const pathGen = geoPath(projection)

// Small north-eastern states get their label (and glyphs) in a stack off the
// coast with a leader line, the way print atlases do it.
const STACKED = ['VT', 'NH', 'MA', 'RI', 'CT', 'NJ', 'DE', 'MD', 'DC']
const STACK_X = 965, STACK_Y0 = 175, STACK_DY = 24

// Off-projection jurisdictions drawn as boxes along the bottom edge.
const BOXES = { DC: [560, 580], PR: [606, 580], GU: [652, 580], VI: [698, 580] }
const BOX = 28

// Labels that would sit awkwardly at the raw centroid.
const NUDGE = { FL: [12, 0], LA: [-8, 0], MI: [10, 14], ID: [0, 12], HI: [10, 0], AK: [0, 0] }

function useGeometry() {
  return useMemo(() => {
    const fc = feature(statesTopo, statesTopo.objects.states)
    const out = {}
    for (const f of fc.features) {
      const code = FIPS[f.id]
      if (!code || code === 'DC') continue
      const d = pathGen(f)
      if (!d) continue
      const [cx, cy] = pathGen.centroid(f)
      const n = NUDGE[code] || [0, 0]
      out[code] = { d, centroid: [cx + n[0], cy + n[1]] }
    }
    return out
  }, [])
}

function anchorFor(code, geo) {
  const i = STACKED.indexOf(code)
  if (i >= 0 && !BOXES[code]) return [STACK_X, STACK_Y0 + i * STACK_DY]
  if (BOXES[code]) return BOXES[code]
  return geo[code]?.centroid
}

export default function USMap({ states, layer, onStateClick }) {
  const [hover, setHover] = useState(null)
  const [mouse, setMouse] = useState([0, 0])
  const geo = useGeometry()
  const byCode = useMemo(() => Object.fromEntries(states.map((s) => [s.state_code, s])), [states])

  const legend = layer === 'stance'
    ? Object.keys(STANCE_COLORS).map((k) => [STANCE_COLORS[k], STANCE_LABELS[k]])
    : Object.keys(STAGE_COLORS).map((k) => [STAGE_COLORS[k], STAGE_LABELS[k]])

  const enter = (s) => (e) => { setHover(s); setMouse([e.clientX, e.clientY]) }
  const move = (e) => setMouse([e.clientX, e.clientY])
  const leave = () => setHover(null)

  // Glyphs sit above-left / above-right of a label on the map, but to the
  // right of it in the north-east stack so they don't collide with neighbors.
  const Glyphs = ({ s, at, stacked }) => {
    const [x, y] = at
    const lean = s.local_signal?.leaning
    const dot = stacked ? [x + 17, y] : [x + 11, y - 11]
    const sq = stacked ? [x + 24, y - 4] : [x - 15, y - 15]
    return (
      <>
        {s.bill_counts?.pending > 0 && (
          <circle cx={dot[0]} cy={dot[1]} r={4} className="pending-dot">
            <title>{s.bill_counts.pending} bills pending review</title>
          </circle>
        )}
        {lean && (
          <rect x={sq[0]} y={sq[1]} width={8} height={8} rx={1.5}
            className="local-glyph" fill={LEANING_COLORS[lean]}>
            <title>{s.local_signal.active} active local action(s), leaning {lean}</title>
          </rect>
        )}
      </>
    )
  }

  return (
    <div className="us-map-container">
      <div className="map-header">
        <h2>{layer === 'stance' ? 'Regulatory stance (researched)' : 'Legislation status'}</h2>
        <p>
          {layer === 'stance'
            ? 'Manual classification of each state\'s guidance and policy. Gray = nobody has researched it yet.'
            : 'Strongest stage among the bills a reviewer has included; resolutions never count. Gray = no included bills.'}
          {' '}Small squares mark states where districts or cities have acted on their own.
        </p>
      </div>

      <div className="map-frame">
        <svg viewBox={`0 0 ${W} ${H}`} className="us-map-svg" preserveAspectRatio="xMidYMid meet">
          {/* state shapes */}
          <g className="shapes">
            {Object.entries(geo).map(([code, g]) => {
              const s = byCode[code]
              if (!s) return null
              const isHover = hover?.state_code === code
              return (
                <path key={code} d={g.d} className={`state-shape ${isHover ? 'hovered' : ''}`}
                  fill={stateColor(s, layer)}
                  onClick={() => onStateClick(code)}
                  onMouseEnter={enter(s)} onMouseMove={move} onMouseLeave={leave} />
              )
            })}
          </g>

          {/* leader lines + labels + glyphs for shapes */}
          <g className="labels" pointerEvents="none">
            {Object.entries(geo).map(([code, g]) => {
              const s = byCode[code]
              if (!s) return null
              const at = anchorFor(code, geo)
              const stacked = STACKED.includes(code)
              return (
                <g key={code}>
                  {stacked && (
                    <line x1={g.centroid[0]} y1={g.centroid[1]} x2={at[0] - 14} y2={at[1]} className="leader" />
                  )}
                  <text x={at[0]} y={at[1]} textAnchor="middle" dominantBaseline="middle"
                    className={`state-label ${stacked ? 'stacked' : ''}`}>{code}</text>
                  <Glyphs s={s} at={at} stacked={stacked} />
                </g>
              )
            })}
          </g>

          {/* DC + territories as boxes */}
          <g className="boxes">
            {Object.entries(BOXES).map(([code, [x, y]]) => {
              const s = byCode[code]
              if (!s) return null
              const isHover = hover?.state_code === code
              return (
                <g key={code} onClick={() => onStateClick(code)}
                  onMouseEnter={enter(s)} onMouseMove={move} onMouseLeave={leave}>
                  <rect x={x - BOX / 2} y={y - BOX / 2} width={BOX} height={BOX} rx={4}
                    className={`state-shape box ${isHover ? 'hovered' : ''}`} fill={stateColor(s, layer)} />
                  <text x={x} y={y} textAnchor="middle" dominantBaseline="middle" className="state-label" pointerEvents="none">{code}</text>
                  <g pointerEvents="none"><Glyphs s={s} at={[x, y]} /></g>
                </g>
              )
            })}
            <text x={560 - BOX / 2} y={606} className="inset-caption">DC &amp; territories</text>
          </g>
        </svg>

        {hover && (
          <div className="map-tooltip" style={{ left: mouse[0] + 14, top: mouse[1] + 14 }}>
            <div className="tt-state">{hover.state_name}</div>
            <div className="tt-line">
              {layer === 'stance' ? STANCE_LABELS[stanceKey(hover)] : STAGE_LABELS[hover.legislation_stage || 'none']}
            </div>
            <div className="tt-line">
              {hover.headline_bill
                ? `${hover.headline_bill.bill_number} · ${hover.headline_bill.bill_status}${hover.headline_bill.is_resolution ? ' (resolution)' : ''}`
                : 'No headline bill'}
            </div>
            <div className="tt-muted">
              {hover.bill_counts.included} included · {hover.bill_counts.pending} pending · {hover.bill_counts.held} held
            </div>
            {hover.local_signal?.headline ? (
              <div className="tt-local" style={{ borderColor: LEANING_COLORS[hover.local_signal.leaning] }}>
                <strong>{hover.local_signal.headline.jurisdiction}</strong>
                {' — '}{ACTION_LABELS[hover.local_signal.headline.action_type]}
                {hover.local_signal.headline.grade_band ? ` (${hover.local_signal.headline.grade_band})` : ''}
                {hover.local_signal.count > 1 ? ` +${hover.local_signal.count - 1} more` : ''}
              </div>
            ) : (
              <div className="tt-muted">
                {hover.research_status === 'RESEARCHED' ? 'Guidance researched' : 'Guidance not yet researched'}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="map-legend">
        {legend.map(([color, label]) => (
          <div className="legend-item" key={label}>
            <div className="legend-color" style={{ backgroundColor: color }} />
            <span>{label}</span>
          </div>
        ))}
        <div className="legend-item">
          <div className="legend-color pending-swatch" />
          <span>Has bills pending review</span>
        </div>
        {Object.keys(LEANING_COLORS).map((k) => (
          <div className="legend-item" key={k}>
            <div className="legend-color local-swatch" style={{ backgroundColor: LEANING_COLORS[k] }} />
            <span>{LEANING_LABELS[k]}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
