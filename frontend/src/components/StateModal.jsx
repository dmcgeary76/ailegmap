import { useEffect, useState } from 'react'
import './StateModal.css'
import { api, STAGE_LABELS, STANCE_LABELS, stanceKey, LEANING_COLORS, ACTION_LABELS, DIRECTION_LABELS } from '../api'

const fmtDate = (v) => (v ? new Date(v).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) : 'N/A')

export default function StateModal({ stateCode, onClose }) {
  const [state, setState] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setState(null)
    api.state(stateCode).then(setState).catch(() => setError('Could not load this state.'))
  }, [stateCode])

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{state ? state.state_name : stateCode}</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">×</button>
        </div>

        <div className="modal-body">
          {error && <p className="error">{error}</p>}
          {!state && !error && <p className="text-muted">Loading…</p>}
          {state && <Body state={state} />}
        </div>
      </div>
    </div>
  )
}

function Body({ state }) {
  const researched = state.research_status === 'RESEARCHED'
  const counts = state.bill_counts
  return (
    <>
      <div className="info-section">
        <h3>At a glance</h3>
        <div className="info-grid">
          <div className="info-item">
            <label>Legislation</label>
            <span className={`stage-badge stage-${state.legislation_stage || 'none'}`}>
              {STAGE_LABELS[state.legislation_stage || 'none']}
            </span>
          </div>
          <div className="info-item">
            <label>Regulatory stance</label>
            {researched ? (
              <span className={`stance-badge stance-${state.regulatory_stance.toLowerCase()}`}>
                {STANCE_LABELS[stanceKey(state)]}
              </span>
            ) : (
              <span className="stance-badge stance-unassessed">Not yet assessed</span>
            )}
          </div>
          {researched && (
            <div className="info-item">
              <label>Maturity</label>
              <span className="maturity-badge">{state.maturity.replace('_', ' ')}</span>
            </div>
          )}
        </div>
      </div>

      <LocalActions state={state} />

      <div className="info-section">
        <h3>Bills on the map ({counts.included})</h3>
        {state.bills.length === 0 && (
          <p className="text-muted">
            {counts.total === 0
              ? 'LegiScan returned no K-12 AI bills for this jurisdiction.'
              : `${counts.total} bills were found, none included yet — ${counts.pending} pending review.`}
          </p>
        )}
        <ul className="bill-list">
          {state.bills.map((b, i) => (
            <li key={b.id} className={i === 0 ? 'headline' : ''}>
              <div className="bill-row">
                <a href={b.bill_url} target="_blank" rel="noopener noreferrer" className="bill-number">{b.bill_number}</a>
                <span className={`stage-chip stage-${b.bill_stage || 'none'}`}>{b.bill_status || 'Unknown'}</span>
                {b.decision === 'INCLUDED' && <span className="chip-muted" title="Included by a reviewer">reviewed</span>}
                {i === 0 && <span className="chip-muted">headline</span>}
              </div>
              <div className="bill-title">{b.bill_title}</div>
              {b.last_action && (
                <div className="bill-action text-muted">
                  {b.last_action}{b.last_action_date ? ` · ${b.last_action_date}` : ''}
                </div>
              )}
            </li>
          ))}
        </ul>
        {counts.held > 0 && (
          <p className="text-muted small">
            {counts.held} more bill{counts.held === 1 ? '' : 's'} held off the map
            ({counts.pending} pending review, {counts.manually_excluded} excluded). Use the Review tab to change that.
          </p>
        )}
      </div>

      {researched ? (
        <>
          {state.guidance_exists && (
            <div className="info-section">
              <h3>State guidance</h3>
              <div className="info-item"><label>Issued by</label><span>{state.guidance_issued_by || 'N/A'}</span></div>
              <div className="info-item"><label>Type</label><span>{state.guidance_type}</span></div>
              {state.guidance_core_principles?.length > 0 && (
                <div className="info-item">
                  <label>Core principles</label>
                  <div className="tag-list">{state.guidance_core_principles.map((p) => <span key={p} className="tag">{p}</span>)}</div>
                </div>
              )}
              {state.guidance_url && (
                <div className="info-item"><label>Document</label>
                  <a href={state.guidance_url} target="_blank" rel="noopener noreferrer">View guidance →</a>
                </div>
              )}
            </div>
          )}
          {state.key_focus_areas?.length > 0 && (
            <div className="info-section"><h3>Focus areas</h3>
              <div className="tag-list">{state.key_focus_areas.map((a) => <span key={a} className="tag">{a}</span>)}</div>
            </div>
          )}
          {state.unique_context && <div className="info-section"><h3>Context</h3><p>{state.unique_context}</p></div>}
          {state.notes && <div className="info-section"><h3>Notes</h3><p>{state.notes}</p></div>}
          {state.sources?.length > 0 && (
            <div className="info-section"><h3>Sources</h3>
              <ul className="sources">{state.sources.map((u) => <li key={u}><a href={u} target="_blank" rel="noopener noreferrer">{u}</a></li>)}</ul>
            </div>
          )}
        </>
      ) : (
        <div className="info-section">
          <h3>State guidance</h3>
          <p className="text-muted">Not researched yet. Add <code>backend/data/profiles/{state.state_code}.json</code> and run <code>python -m app.seed</code>.</p>
        </div>
      )}

      <div className="info-section">
        <span className="text-muted small">Profile last updated {fmtDate(state.last_updated)}</span>
      </div>
    </>
  )
}

const fmtEnrollment = (n) => (n >= 1000 ? `~${Math.round(n / 1000)}k students` : `~${n} students`)

function LocalActions({ state }) {
  const sig = state.local_signal
  const actions = state.local_actions || []
  return (
    <div className="info-section">
      <h3>
        Local actions ({actions.length})
        {sig.leaning && (
          <span className="leaning-badge" style={{ background: LEANING_COLORS[sig.leaning] }}>
            {sig.leaning}
          </span>
        )}
      </h3>
      {actions.length === 0 ? (
        <p className="text-muted">
          No notable district, city or county actions recorded. Add one to{' '}
          <code>backend/data/local_actions/{state.state_code}.json</code> if it meets the inclusion rule.
        </p>
      ) : (
        <ul className="action-list">
          {actions.map((a) => (
            <li key={a.id} className={`action status-${a.status}`}>
              <div className="action-row">
                <strong>{a.jurisdiction}</strong>
                <span className={`action-chip dir-${a.direction < 0 ? 'neg' : a.direction > 0 ? 'pos' : 'zero'}`}>
                  {ACTION_LABELS[a.action_type] || a.action_type} · {DIRECTION_LABELS[String(a.direction)]}
                </span>
                <span className={`status-chip status-${a.status}`}>{a.status}</span>
              </div>
              <div className="action-meta text-muted small">
                {[a.jurisdiction_type, a.grade_band, a.applies_to && `applies to ${a.applies_to}`,
                  a.enrollment && fmtEnrollment(a.enrollment)].filter(Boolean).join(' · ')}
                {a.effective_from && ` · from ${a.effective_from}`}
                {a.effective_until && ` to ${a.effective_until}`}
              </div>
              <p className="action-summary">{a.summary}</p>
              {a.authority && <div className="text-muted small">Authority: {a.authority}</div>}
              {a.notes && <details className="action-notes"><summary>Notes</summary><p>{a.notes}</p></details>}
              {a.sources?.length > 0 && (
                <div className="action-sources small">
                  {a.sources.map((u, i) => (
                    <a key={u} href={u} target="_blank" rel="noopener noreferrer">source {i + 1}</a>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
