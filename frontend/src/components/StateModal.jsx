import './StateModal.css'

export default function StateModal({ state, onClose }) {
  if (!state) return null

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    })
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{state.state_name} ({state.state_code})</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          <div className="info-section">
            <h3>Classification</h3>
            <div className="info-grid">
              <div className="info-item">
                <label>Regulatory Stance</label>
                <span className={`stance-badge stance-${state.regulatory_stance.toLowerCase()}`}>
                  {state.regulatory_stance}
                </span>
              </div>
              <div className="info-item">
                <label>Maturity Level</label>
                <span className="maturity-badge">{state.maturity}</span>
              </div>
            </div>
          </div>

          {state.bill_number && (
            <div className="info-section">
              <h3>Legislation</h3>
              <div className="info-item">
                <label>Bill Number</label>
                <span>{state.bill_number}</span>
              </div>
              {state.bill_title && (
                <div className="info-item">
                  <label>Bill Title</label>
                  <span>{state.bill_title}</span>
                </div>
              )}
              <div className="info-item">
                <label>Status</label>
                <span>{state.bill_status || 'Unknown'}</span>
              </div>
              {state.bill_status_details && (
                <div className="info-item">
                  <label>Status Details</label>
                  <span>{state.bill_status_details}</span>
                </div>
              )}
              {state.bill_url && (
                <div className="info-item">
                  <label>Bill Link</label>
                  <a href={state.bill_url} target="_blank" rel="noopener noreferrer">
                    View Bill →
                  </a>
                </div>
              )}
            </div>
          )}

          {state.guidance_exists && (
            <div className="info-section">
              <h3>State Guidance</h3>
              <div className="info-item">
                <label>Issued By</label>
                <span>{state.guidance_issued_by || 'N/A'}</span>
              </div>
              <div className="info-item">
                <label>Guidance Type</label>
                <span>{state.guidance_type}</span>
              </div>
              {state.guidance_core_principles && state.guidance_core_principles.length > 0 && (
                <div className="info-item">
                  <label>Core Principles</label>
                  <div className="tag-list">
                    {state.guidance_core_principles.map((principle, idx) => (
                      <span key={idx} className="tag">{principle}</span>
                    ))}
                  </div>
                </div>
              )}
              {state.guidance_url && (
                <div className="info-item">
                  <label>Guidance Document</label>
                  <a href={state.guidance_url} target="_blank" rel="noopener noreferrer">
                    View Guidance →
                  </a>
                </div>
              )}
            </div>
          )}

          {state.key_focus_areas && state.key_focus_areas.length > 0 && (
            <div className="info-section">
              <h3>Focus Areas</h3>
              <div className="tag-list">
                {state.key_focus_areas.map((area, idx) => (
                  <span key={idx} className="tag">{area}</span>
                ))}
              </div>
            </div>
          )}

          {state.unique_context && (
            <div className="info-section">
              <h3>Regional Context</h3>
              <p>{state.unique_context}</p>
            </div>
          )}

          {state.notes && (
            <div className="info-section">
              <h3>Notes</h3>
              <p>{state.notes}</p>
            </div>
          )}

          <div className="info-section">
            <label className="text-muted">Last Updated</label>
            <span className="text-muted">{formatDate(state.last_updated)}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
