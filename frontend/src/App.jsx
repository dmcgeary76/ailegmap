import { useState, useEffect } from 'react'
import axios from 'axios'
import './App.css'
import Dashboard from './components/Dashboard'
import USMap from './components/USMap'
import StateModal from './components/StateModal'
import ReviewQueue from './components/ReviewQueue'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [view, setView] = useState('map') // 'map' | 'review'
  const [states, setStates] = useState([])
  const [summary, setSummary] = useState(null)
  const [selectedState, setSelectedState] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filters, setFilters] = useState({
    stance: null,
    maturity: null,
  })

  // Fetch all states and summary on mount and when filters change
  useEffect(() => {
    fetchData()
  }, [filters])

  const fetchData = async () => {
    try {
      setLoading(true)

      // Build query params
      const params = new URLSearchParams()
      if (filters.stance) params.append('stance', filters.stance)
      if (filters.maturity) params.append('maturity', filters.maturity)

      const [statesRes, summaryRes] = await Promise.all([
        axios.get(`${API_URL}/api/states?${params}`),
        axios.get(`${API_URL}/api/dashboard/summary`),
      ])

      setStates(statesRes.data)
      setSummary(summaryRes.data)
      setError(null)
    } catch (err) {
      console.error('Error fetching data:', err)
      setError('Failed to load data. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  const handleStateClick = (stateCode) => {
    const state = states.find(s => s.state_code === stateCode)
    setSelectedState(state)
  }

  const handleCloseModal = () => {
    setSelectedState(null)
  }

  const handleFilterChange = (filterType, value) => {
    setFilters(prev => ({
      ...prev,
      [filterType]: value === null ? null : value
    }))
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>K-12 AI Legislative Map</h1>
        <p>Tracking AI legislation across U.S. state education systems</p>
        <nav className="app-nav">
          <button
            className={view === 'map' ? 'nav-tab active' : 'nav-tab'}
            onClick={() => setView('map')}
          >
            Map
          </button>
          <button
            className={view === 'review' ? 'nav-tab active' : 'nav-tab'}
            onClick={() => setView('review')}
          >
            Review Queue
          </button>
        </nav>
      </header>

      {view === 'review' ? (
        <ReviewQueue />
      ) : error && !states.length ? (
        <div className="error-container"><p>{error}</p></div>
      ) : (
        <>
          {loading && <div className="loading">Loading...</div>}

          {!loading && (
            <div className="app-layout">
              <aside className="sidebar">
                {summary && <Dashboard summary={summary} onFilterChange={handleFilterChange} />}
              </aside>

              <main className="main-content">
                {states.length > 0 ? (
                  <USMap states={states} onStateClick={handleStateClick} />
                ) : (
                  <p className="no-data">No states found</p>
                )}
              </main>
            </div>
          )}

          {selectedState && (
            <StateModal state={selectedState} onClose={handleCloseModal} />
          )}
        </>
      )}
    </div>
  )
}

export default App
