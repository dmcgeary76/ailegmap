import React, { useState, useEffect } from 'react';
import './USMap.css';

const STANCE_COLORS = {
  PROHIBIT: '#dc2626',
  RESTRICT: '#ea580c',
  REGULATE: '#eab308',
  SUPPORT: '#16a34a',
  MANDATE: '#2563eb',
  ABSENT: '#d1d5db',
};

const TERRITORY_POSITIONS = {
  GU: { x: 80, y: 650, label: 'Guam' },
  PR: { x: 160, y: 650, label: 'Puerto Rico' },
  VI: { x: 240, y: 650, label: 'Virgin Islands' },
};

export default function USMap({ states, onStateClick }) {
  const [topoData, setTopoData] = useState(null);
  const [hoveredState, setHoveredState] = useState(null);
  const [tooltip, setTooltip] = useState(null);

  useEffect(() => {
    // Load TopoJSON data
    fetch('https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json')
      .then(r => r.json())
      .then(data => setTopoData(data))
      .catch(err => console.error('Failed to load map data:', err));
  }, []);

  if (!topoData) return <div className="us-map-container"><p>Loading map...</p></div>;

  const stateMap = {};
  states.forEach(state => {
    stateMap[state.state_code] = state;
  });

  return (
    <div className="us-map-container">
      <div className="map-header">
        <h2>Interactive US Map</h2>
        <p>Click a state or territory to view legislation details</p>
      </div>

      <svg
        viewBox="0 0 960 750"
        className="us-map-svg"
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Main map states */}
        <MapStates
          topoData={topoData}
          stateMap={stateMap}
          hoveredState={hoveredState}
          onStateClick={onStateClick}
          onHover={(code, data) => {
            setHoveredState(code);
            if (data) {
              setTooltip({
                state: data.state_name,
                bills: (data.bill_number ? 1 : 0) + (data.additional_bills?.length || 0),
                stance: data.regulatory_stance,
              });
            }
          }}
          onLeave={() => {
            setHoveredState(null);
            setTooltip(null);
          }}
        />

        {/* Territory insets */}
        <g className="territories">
          {['GU', 'PR', 'VI'].map(code => {
            const territory = stateMap[code];
            const pos = TERRITORY_POSITIONS[code];
            const color = territory ? STANCE_COLORS[territory.regulatory_stance] : STANCE_COLORS.ABSENT;
            const billCount = territory ? (territory.bill_number ? 1 : 0) + (territory.additional_bills?.length || 0) : 0;

            return (
              <g key={code}>
                {/* Inset box */}
                <rect
                  x={pos.x - 20}
                  y={pos.y - 20}
                  width={40}
                  height={40}
                  fill={color}
                  stroke="white"
                  strokeWidth="2"
                  rx="4"
                  className="territory-box"
                  style={{ cursor: territory ? 'pointer' : 'not-allowed', opacity: territory ? 1 : 0.6 }}
                  onClick={() => territory && onStateClick(code)}
                  onMouseEnter={() => {
                    setHoveredState(code);
                    if (territory) {
                      setTooltip({
                        state: territory.state_name,
                        bills: billCount,
                        stance: territory.regulatory_stance,
                      });
                    }
                  }}
                  onMouseLeave={() => {
                    setHoveredState(null);
                    setTooltip(null);
                  }}
                />

                {/* Territory code */}
                <text
                  x={pos.x}
                  y={pos.y}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  className="territory-label"
                  pointerEvents="none"
                >
                  {code}
                </text>

                {/* Connecting line and label */}
                <line
                  x1={pos.x}
                  y1={pos.y + 22}
                  x2={pos.x}
                  y2={pos.y + 35}
                  stroke="#d1d5db"
                  strokeWidth="1"
                  className="territory-connector"
                />
                <text
                  x={pos.x}
                  y={pos.y + 50}
                  textAnchor="middle"
                  className="territory-name"
                >
                  {pos.label}
                </text>
              </g>
            );
          })}
        </g>

        {/* Tooltip */}
        {tooltip && (
          <g className="tooltip-group">
            <rect
              x={hoveredState === 'GU' ? 100 : hoveredState === 'PR' ? 170 : 210}
              y="30"
              width="140"
              height="60"
              fill="white"
              stroke="#d1d5db"
              strokeWidth="1"
              rx="6"
              className="tooltip-bg"
            />
            <text x="110" y="50" className="tooltip-state">{tooltip.state}</text>
            <text x="110" y="65" className="tooltip-stance">{tooltip.stance}</text>
            <text x="110" y="80" className="tooltip-bills">{tooltip.bills} bill{tooltip.bills !== 1 ? 's' : ''}</text>
          </g>
        )}
      </svg>

      {/* Legend */}
      <div className="map-legend">
        <div className="legend-item">
          <div className="legend-color" style={{ backgroundColor: '#dc2626' }} />
          <span>Prohibits</span>
        </div>
        <div className="legend-item">
          <div className="legend-color" style={{ backgroundColor: '#ea580c' }} />
          <span>Restricts</span>
        </div>
        <div className="legend-item">
          <div className="legend-color" style={{ backgroundColor: '#eab308' }} />
          <span>Regulates</span>
        </div>
        <div className="legend-item">
          <div className="legend-color" style={{ backgroundColor: '#16a34a' }} />
          <span>Supports</span>
        </div>
        <div className="legend-item">
          <div className="legend-color" style={{ backgroundColor: '#2563eb' }} />
          <span>Mandates</span>
        </div>
        <div className="legend-item">
          <div className="legend-color" style={{ backgroundColor: '#d1d5db' }} />
          <span>No Legislation</span>
        </div>
      </div>
    </div>
  );
}

// Helper component to render map states from TopoJSON
function MapStates({ topoData, stateMap, hoveredState, onStateClick, onHover, onLeave }) {
  const features = topoData.objects.states.geometries;
  const stateIds = topoData.objects.states.geometries.map((_, i) => i);

  // Simple mercator projection (approximate)
  const project = (lon, lat) => {
    const x = (lon + 180) * (960 / 360);
    const y = (90 - lat) * (600 / 180);
    return [x, y];
  };

  // Convert TopoJSON geometry to SVG path
  const geometryToPath = (geometry) => {
    if (!geometry) return '';

    const types = {
      Point: (coords) => {
        const [x, y] = project(coords[0], coords[1]);
        return `M${x},${y}`;
      },
      LineString: (coords) => {
        return coords.map((c, i) => {
          const [x, y] = project(c[0], c[1]);
          return `${i === 0 ? 'M' : 'L'}${x},${y}`;
        }).join('');
      },
      Polygon: (coords) => {
        return coords.map((ring, i) => {
          return ring.map((c, j) => {
            const [x, y] = project(c[0], c[1]);
            return `${j === 0 ? 'M' : 'L'}${x},${y}`;
          }).join('') + 'Z';
        }).join('');
      },
      MultiPolygon: (coords) => {
        return coords.map(polygon => types.Polygon(polygon)).join('');
      },
    };

    return types[geometry.type] ? types[geometry.type](geometry.arcs || geometry.coordinates) : '';
  };

  return (
    <>
      {/* Simplified state rendering - using state center labels for now */}
      {/* Full SVG path rendering would require detailed TopoJSON arcs decoding */}
      <g className="states">
        {Object.entries(stateMap).filter(([code]) => code.length === 2 && !['GU', 'PR', 'VI'].includes(code)).map(([code, data]) => {
          const isHovered = hoveredState === code;
          const color = STANCE_COLORS[data.regulatory_stance];
          const billCount = (data.bill_number ? 1 : 0) + (data.additional_bills?.length || 0);

          return (
            <g
              key={code}
              className={`state ${isHovered ? 'hovered' : ''}`}
              onClick={() => onStateClick(code)}
              onMouseEnter={() => onHover(code, data)}
              onMouseLeave={onLeave}
            >
              {/* State label as placeholder for actual SVG path */}
              <circle
                cx={getStateX(code)}
                cy={getStateY(code)}
                r="18"
                fill={color}
                stroke={isHovered ? 'white' : '#ffffff'}
                strokeWidth={isHovered ? '3' : '1'}
                style={{ cursor: 'pointer' }}
                opacity={data ? 1 : 0.6}
              />
              <text
                x={getStateX(code)}
                y={getStateY(code)}
                textAnchor="middle"
                dominantBaseline="middle"
                className="state-label"
                pointerEvents="none"
                fontSize="11"
                fontWeight="bold"
                fill="white"
              >
                {code}
              </text>
            </g>
          );
        })}
      </g>
    </>
  );
}

// Approximate state center coordinates (scaled to 960x750 viewBox)
const STATE_CENTERS = {
  WA: [100, 90], OR: [80, 150], CA: [80, 240], NV: [140, 240], ID: [180, 120],
  MT: [240, 100], WY: [280, 140], UT: [220, 220], CO: [300, 220], AZ: [240, 300],
  NM: [300, 320], ND: [360, 90], SD: [380, 150], NE: [360, 210], KS: [360, 270],
  OK: [380, 320], TX: [400, 380], MN: [440, 110], IA: [420, 180], MO: [460, 260],
  AR: [460, 300], LA: [480, 380], WI: [500, 140], IL: [500, 220], MS: [480, 340],
  MI: [560, 150], IN: [540, 210], OH: [580, 210], KY: [560, 270], TN: [520, 310],
  WV: [600, 240], VA: [640, 250], NC: [680, 290], SC: [680, 340], GA: [680, 360],
  FL: [720, 430], PA: [660, 180], MD: [720, 200], DE: [740, 210], NJ: [760, 180],
  NY: [700, 150], CT: [780, 170], RI: [800, 180], MA: [800, 160], VT: [760, 130],
  NH: [820, 140], ME: [840, 110], AK: [100, 580], HI: [160, 600],
};

const getStateX = (code) => STATE_CENTERS[code]?.[0] || 400;
const getStateY = (code) => STATE_CENTERS[code]?.[1] || 300;
