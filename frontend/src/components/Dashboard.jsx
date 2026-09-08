import './Dashboard.css'
import { STAGE_COLORS, STAGE_LABELS, STANCE_COLORS, STANCE_LABELS } from '../api'

const STAGES = ['passed', 'debated', 'introduced', 'failed', 'none']
const STANCES = ['PROHIBIT', 'RESTRICT', 'REGULATE', 'SUPPORT', 'MANDATE', 'ABSENT']

function fmtDate(iso) {
  if (!iso) return 'never'
  return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

export default function Dashboard({ summary, layer, onLayerChange, filter, onFilterChange }) {
  const s = summary
  const active = (key, value) => filter && filter[key] === value

  return (
    <div className="dashboard">
      <div className="dashboard-card">
        <h2>Overview</h2>
        <div className="stat-grid">
          <div className="stat">
            <div className="stat-value">{s.states_with_included_bills}</div>
            <div className="stat-label">Jurisdictions with included bills</div>
          </div>
          <div className="stat">
            <div className="stat-value">{s.states_by_legislation_stage.passed}</div>
            <div className="stat-label">With a passed bill</div>
          </div>
          <div className="stat">
            <div className="stat-value">{s.states_researched}</div>
            <div className="stat-label">Guidance researched</div>
          </div>
          <div className="stat">
            <div className="stat-value">{s.local_actions?.active ?? 0}</div>
            <div className="stat-label">Active local actions ({s.local_actions?.states ?? 0} states)</div>
          </div>
        </div>
        <div className="review-progress">
          <div className="rp-bar">
            <span className="rp-inc" style={{ flex: s.bills.included }} title={`${s.bills.included} included`} />
            <span className="rp-pend" style={{ flex: s.bills.pending }} title={`${s.bills.pending} pending`} />
            <span className="rp-exc" style={{ flex: s.bills.excluded }} title={`${s.bills.excluded} excluded`} />
          </div>
          <div className="rp-caption">
            {s.bills.total} bills found · {s.bills.included} on map · {s.bills.pending} pending review
          </div>
          <div className="rp-caption muted">Last LegiScan sync: {fmtDate(s.last_sync)}</div>
        </div>
      </div>

      <div className="dashboard-card">
        <h3>Color the map by</h3>
        <div className="layer-toggle">
          <button className={layer === 'legislation' ? 'active' : ''} onClick={() => { onLayerChange('legislation'); onFilterChange(null) }}>
            Legislation status
          </button>
          <button className={layer === 'stance' ? 'active' : ''} onClick={() => { onLayerChange('stance'); onFilterChange(null) }}>
            Regulatory stance
          </button>
        </div>

        {layer === 'legislation' ? (
          <div className="filter-options">
            <button className={`filter-btn ${!filter ? 'active' : ''}`} onClick={() => onFilterChange(null)}>All</button>
            {STAGES.map((k) => (
              <button
                key={k}
                className={`filter-btn ${active('legislation_stage', k) ? 'active' : ''}`}
                onClick={() => onFilterChange(active('legislation_stage', k) ? null : { legislation_stage: k })}
              >
                <span className="swatch" style={{ background: STAGE_COLORS[k] }} />
                {STAGE_LABELS[k]}
                <span className="count">{s.states_by_legislation_stage[k] || 0}</span>
              </button>
            ))}
          </div>
        ) : (
          <div className="filter-options">
            <button className={`filter-btn ${!filter ? 'active' : ''}`} onClick={() => onFilterChange(null)}>All</button>
            {STANCES.map((k) => (
              <button
                key={k}
                className={`filter-btn ${active('stance', k) ? 'active' : ''}`}
                onClick={() => onFilterChange(active('stance', k) ? null : { stance: k })}
              >
                <span className="swatch" style={{ background: STANCE_COLORS[k] }} />
                {STANCE_LABELS[k]}
                <span className="count">{s.states_by_stance[k] || 0}</span>
              </button>
            ))}
            <p className="muted small">
              {s.jurisdictions - s.states_researched} jurisdictions not yet researched.
            </p>
          </div>
        )}
      </div>

      {s.recent_status_changes.length > 0 && (
        <div className="dashboard-card">
          <h3>Recent status changes</h3>
          <ul className="changes">
            {s.recent_status_changes.map((c, i) => (
              <li key={i}>
                <strong>{c.state_code} {c.bill_number}</strong> {c.old_status || '—'} → {c.new_status}
                <span className="muted"> · {fmtDate(c.changed_at)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
