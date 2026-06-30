import { useState } from 'react'
import './Dashboard.css'

export default function Dashboard({ summary, onFilterChange }) {
  const [expandedSection, setExpandedSection] = useState(null)

  const toggleSection = (section) => {
    setExpandedSection(expandedSection === section ? null : section)
  }

  const handleFilterSelect = (filterType, value) => {
    onFilterChange(filterType, value)
  }

  if (!summary) return <div>Loading summary...</div>

  const stanceOptions = [
    { label: 'Prohibit', value: 'PROHIBIT', color: 'prohibit' },
    { label: 'Restrict', value: 'RESTRICT', color: 'restrict' },
    { label: 'Regulate', value: 'REGULATE', color: 'regulate' },
    { label: 'Support', value: 'SUPPORT', color: 'support' },
    { label: 'Mandate', value: 'MANDATE', color: 'mandate' },
    { label: 'Absent', value: 'ABSENT', color: 'absent' },
  ]

  const maturityOptions = [
    { label: 'Nascent', value: 'NASCENT' },
    { label: 'In Progress', value: 'IN_PROGRESS' },
    { label: 'Active', value: 'ACTIVE' },
    { label: 'Mature', value: 'MATURE' },
  ]

  return (
    <div className="dashboard">
      <div className="dashboard-card">
        <h2>Dashboard</h2>

        <div className="stat-grid">
          <div className="stat">
            <div className="stat-value">{summary.total_states}</div>
            <div className="stat-label">Total States</div>
          </div>
          <div className="stat">
            <div className="stat-value">{summary.states_with_legislation}</div>
            <div className="stat-label">With Legislation</div>
          </div>
          <div className="stat">
            <div className="stat-value">{summary.states_with_guidance}</div>
            <div className="stat-label">With Guidance</div>
          </div>
        </div>
      </div>

      <div className="dashboard-card">
        <button
          className="section-toggle"
          onClick={() => toggleSection('stance')}
        >
          <span>Filter by Stance</span>
          <span className="toggle-icon">{expandedSection === 'stance' ? '▼' : '▶'}</span>
        </button>
        {expandedSection === 'stance' && (
          <div className="filter-options">
            <button className="filter-btn" onClick={() => handleFilterSelect('stance', null)}>
              All Stances
            </button>
            {stanceOptions.map(option => (
              <button
                key={option.value}
                className={`filter-btn stance-${option.color}`}
                onClick={() => handleFilterSelect('stance', option.value)}
              >
                {option.label}
                <span className="count">({summary.states_by_stance[option.value] || 0})</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="dashboard-card">
        <button
          className="section-toggle"
          onClick={() => toggleSection('maturity')}
        >
          <span>Filter by Maturity</span>
          <span className="toggle-icon">{expandedSection === 'maturity' ? '▼' : '▶'}</span>
        </button>
        {expandedSection === 'maturity' && (
          <div className="filter-options">
            <button className="filter-btn" onClick={() => handleFilterSelect('maturity', null)}>
              All Maturity Levels
            </button>
            {maturityOptions.map(option => (
              <button
                key={option.value}
                className="filter-btn"
                onClick={() => handleFilterSelect('maturity', option.value)}
              >
                {option.label}
                <span className="count">({summary.states_by_maturity[option.value] || 0})</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="dashboard-card">
        <h3>Legend</h3>
        <div className="legend">
          <div className="legend-item">
            <div className="legend-color prohibit"></div>
            <span>Prohibit</span>
          </div>
          <div className="legend-item">
            <div className="legend-color restrict"></div>
            <span>Restrict</span>
          </div>
          <div className="legend-item">
            <div className="legend-color regulate"></div>
            <span>Regulate</span>
          </div>
          <div className="legend-item">
            <div className="legend-color support"></div>
            <span>Support</span>
          </div>
          <div className="legend-item">
            <div className="legend-color mandate"></div>
            <span>Mandate</span>
          </div>
          <div className="legend-item">
            <div className="legend-color absent"></div>
            <span>Absent</span>
          </div>
        </div>
      </div>
    </div>
  )
}
