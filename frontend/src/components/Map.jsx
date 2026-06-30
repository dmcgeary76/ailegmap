import './Map.css'
import { useState } from 'react'

// State and territory abbreviation to name mapping
const STATE_NAMES = {
  AL: 'Alabama', AK: 'Alaska', AZ: 'Arizona', AR: 'Arkansas', CA: 'California',
  CO: 'Colorado', CT: 'Connecticut', DE: 'Delaware', FL: 'Florida', GA: 'Georgia',
  HI: 'Hawaii', ID: 'Idaho', IL: 'Illinois', IN: 'Indiana', IA: 'Iowa',
  KS: 'Kansas', KY: 'Kentucky', LA: 'Louisiana', ME: 'Maine', MD: 'Maryland',
  MA: 'Massachusetts', MI: 'Michigan', MN: 'Minnesota', MS: 'Mississippi',
  MO: 'Missouri', MT: 'Montana', NE: 'Nebraska', NV: 'Nevada', NH: 'New Hampshire',
  NJ: 'New Jersey', NM: 'New Mexico', NY: 'New York', NC: 'North Carolina',
  ND: 'North Dakota', OH: 'Ohio', OK: 'Oklahoma', OR: 'Oregon', PA: 'Pennsylvania',
  RI: 'Rhode Island', SC: 'South Carolina', SD: 'South Dakota', TN: 'Tennessee',
  TX: 'Texas', UT: 'Utah', VT: 'Vermont', VA: 'Virginia', WA: 'Washington',
  WV: 'West Virginia', WI: 'Wisconsin', WY: 'Wyoming',
  GU: 'Guam', PR: 'Puerto Rico', VI: 'Virgin Islands',
}

export default function Map({ states, onStateClick }) {
  const [hoverState, setHoverState] = useState(null)

  const getStanceColor = (stance) => {
    const colors = {
      'PROHIBIT': '#dc2626',    // red-600
      'RESTRICT': '#ea580c',    // orange-600
      'REGULATE': '#eab308',    // yellow-500
      'SUPPORT': '#16a34a',     // green-600
      'MANDATE': '#2563eb',     // blue-600
      'ABSENT': '#d1d5db',      // gray-300
    }
    return colors[stance] || '#9e9e9e'
  }

  const stateMap = {}
  states.forEach(state => {
    stateMap[state.state_code] = state
  })

  // Generate buttons for all 50 states (including those without data)
  const allStates = Object.entries(STATE_NAMES)

  return (
    <div className="map-container">
      {/* Stats Header */}
      <div className="map-stats">
        <div className="stat">
          <span className="stat-value">{states.length}</span>
          <span className="stat-label">States Synced</span>
        </div>
        <div className="stat">
          <span className="stat-value">
            {states.reduce((sum, s) => sum + (s.additional_bills?.length || 0) + (s.bill_number ? 1 : 0), 0)}
          </span>
          <span className="stat-label">Bills Tracked</span>
        </div>
      </div>

      {/* Legend */}
      <div className="legend">
        <div className="legend-item">
          <div className="legend-color" style={{ backgroundColor: '#dc2626' }} />
          <span>Prohibits AI</span>
        </div>
        <div className="legend-item">
          <div className="legend-color" style={{ backgroundColor: '#ea580c' }} />
          <span>Restricts AI</span>
        </div>
        <div className="legend-item">
          <div className="legend-color" style={{ backgroundColor: '#eab308' }} />
          <span>Regulates AI</span>
        </div>
        <div className="legend-item">
          <div className="legend-color" style={{ backgroundColor: '#16a34a' }} />
          <span>Supports AI</span>
        </div>
        <div className="legend-item">
          <div className="legend-color" style={{ backgroundColor: '#2563eb' }} />
          <span>Mandates AI</span>
        </div>
        <div className="legend-item">
          <div className="legend-color" style={{ backgroundColor: '#d1d5db' }} />
          <span>No Legislation</span>
        </div>
      </div>

      {/* States Grid */}
      <div className="states-grid">
        {allStates.map(([code, name]) => {
          const stateData = stateMap[code]
          const stance = stateData?.regulatory_stance || 'ABSENT'
          const hasBills = stateData && (stateData.bill_number || stateData.additional_bills?.length > 0)
          const billCount = stateData ?
            (stateData.bill_number ? 1 : 0) + (stateData.additional_bills?.length || 0) : 0

          return (
            <button
              key={code}
              className={`state-button ${hoverState === code ? 'hover' : ''} ${hasBills ? 'has-bills' : ''}`}
              style={{
                backgroundColor: getStanceColor(stance),
                opacity: stateData ? 1 : 0.6,
              }}
              onClick={() => stateData && onStateClick(code)}
              onMouseEnter={() => setHoverState(code)}
              onMouseLeave={() => setHoverState(null)}
              title={stateData ? `${name} - ${stance} (${billCount} bills)` : `${name} - No data`}
              disabled={!stateData}
            >
              <div className="state-code">{code}</div>
              {stateData && (
                <>
                  <div className="state-stance">{stance}</div>
                  <div className="bill-count">{billCount} bill{billCount !== 1 ? 's' : ''}</div>
                </>
              )}
            </button>
          )
        })}
      </div>

      {/* Info Text */}
      <div className="map-footer">
        <p>Click a state to view legislation details • Last updated: {new Date().toLocaleDateString()}</p>
      </div>
    </div>
  )
}
