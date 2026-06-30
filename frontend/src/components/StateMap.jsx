import React, { useState, useEffect } from 'react';
import './StateMap.css';

// Color mapping for regulatory stances
const STANCE_COLORS = {
  PROHIBIT: '#dc2626',    // red-600
  RESTRICT: '#ea580c',    // orange-600
  REGULATE: '#eab308',    // yellow-500
  SUPPORT: '#16a34a',     // green-600
  MANDATE: '#2563eb',     // blue-600
  ABSENT: '#d1d5db',      // gray-300
};

const STANCE_LABELS = {
  PROHIBIT: 'Prohibits AI',
  RESTRICT: 'Restricts AI',
  REGULATE: 'Regulates AI',
  SUPPORT: 'Supports AI',
  MANDATE: 'Mandates AI',
  ABSENT: 'No legislation',
};

export default function StateMap() {
  const [states, setStates] = useState({});
  const [selectedState, setSelectedState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch state legislation data on mount
  useEffect(() => {
    const fetchStates = async () => {
      try {
        const response = await fetch('/api/states');
        if (!response.ok) throw new Error('Failed to fetch states');
        const data = await response.json();

        // Index by state code
        const indexed = {};
        data.forEach(state => {
          indexed[state.state_code] = state;
        });
        setStates(indexed);
      } catch (err) {
        setError(err.message);
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchStates();
  }, []);

  const handleStateClick = (stateCode) => {
    setSelectedState(stateCode);
  };

  if (loading) return <div className="map-container"><p>Loading...</p></div>;
  if (error) return <div className="map-container"><p>Error: {error}</p></div>;

  return (
    <div className="map-container">
      <div className="map-header">
        <h1>US K-12 AI Legislation Map</h1>
        <p>Click a state to view current AI legislation and guidance</p>
        <LegendPanel />
      </div>

      <div className="map-content">
        <SVGMap states={states} onStateClick={handleStateClick} />

        {selectedState && (
          <StateModal
            stateCode={selectedState}
            stateData={states[selectedState]}
            onClose={() => setSelectedState(null)}
          />
        )}
      </div>
    </div>
  );
}

function LegendPanel() {
  return (
    <div className="legend">
      <h3>Regulatory Stance</h3>
      <div className="legend-items">
        {Object.entries(STANCE_LABELS).map(([stance, label]) => (
          <div key={stance} className="legend-item">
            <div
              className="legend-color"
              style={{ backgroundColor: STANCE_COLORS[stance] }}
            />
            <span>{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SVGMap({ states, onStateClick }) {
  // Placeholder SVG - will be replaced with actual US map
  return (
    <div className="map-svg-container">
      <svg viewBox="0 0 960 600" className="us-map">
        {/* This will be populated with state paths */}
        <text x="480" y="300" textAnchor="middle" fontSize="20">
          SVG Map Component
        </text>
        <text x="480" y="330" textAnchor="middle" fontSize="14" fill="#666">
          ({Object.keys(states).length} states synced)
        </text>
      </svg>
    </div>
  );
}

function StateModal({ stateCode, stateData, onClose }) {
  if (!stateData) return null;

  const additionalBills = stateData.additional_bills || [];
  const allBills = [
    {
      bill_number: stateData.bill_number,
      bill_title: stateData.bill_title,
      bill_status: stateData.bill_status,
      bill_url: stateData.bill_url,
    },
    ...additionalBills,
  ].filter(b => b.bill_number);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{stateData.state_name}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          {/* Classification */}
          <div className="classification">
            <div className="stance-badge" style={{ borderColor: STANCE_COLORS[stateData.regulatory_stance] }}>
              <strong>Stance:</strong> {STANCE_LABELS[stateData.regulatory_stance]}
            </div>
            <div className="maturity-badge">
              <strong>Maturity:</strong> {stateData.maturity}
            </div>
          </div>

          {/* Bills */}
          <div className="bills-section">
            <h3>Bills ({allBills.length})</h3>
            <div className="bills-list">
              {allBills.map((bill, idx) => (
                <div key={idx} className="bill-item">
                  <a href={bill.bill_url} target="_blank" rel="noopener noreferrer">
                    <strong>{bill.bill_number}</strong>
                  </a>
                  <p>{bill.bill_title}</p>
                  <span className="bill-status">{bill.bill_status}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Guidance */}
          {stateData.guidance_exists && (
            <div className="guidance-section">
              <h3>State Guidance</h3>
              <p><strong>{stateData.guidance_issued_by}</strong></p>
              {stateData.guidance_url && (
                <a href={stateData.guidance_url} target="_blank" rel="noopener noreferrer">
                  View Guidance →
                </a>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
