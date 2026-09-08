import { useState, useEffect, useCallback } from 'react'
import './App.css'
import { api } from './api'
import Dashboard from './components/Dashboard'
import USMap from './components/USMap'
import StateModal from './components/StateModal'
import ReviewQueue from './components/ReviewQueue'

function App() {
  const [view, setView] = useState('map') // 'map' | 'review'
  const [layer, setLayer] = useState('legislation') // 'legislation' | 'stance'
  const [states, setStates] = useState([])
  const [summary, setSummary] = useState(null)
  const [selectedCode, setSelectedCode] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState(null) // {legislation_stage} | {stance} | null

  const fetchData = useCallback(async () => {
    try {
      setLoading(true)
      const [s, sum] = await Promise.all([api.states(filter || {}), api.summary()])
      setStates(s)
      setSummary(sum)
      setError(null)
    } catch (err) {
      console.error(err)
      setError('Failed to load data. Is the backend running on port 8000?')
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Coming back from the review tab: decisions may have changed the map.
  useEffect(() => {
    if (view === 'map') fetchData()
  }, [view, fetchData])

  return (
    <div className="app">
      <header className="app-header">
        <h1>K-12 AI Legislative Map</h1>
        <p>AI legislation and state guidance across U.S. K-12 education systems</p>
        <nav className="app-nav">
          <button className={view === 'map' ? 'nav-tab active' : 'nav-tab'} onClick={() => setView('map')}>
            Map
          </button>
          <button className={view === 'review' ? 'nav-tab active' : 'nav-tab'} onClick={() => setView('review')}>
            Review bills{summary?.bills?.pending ? ` (${summary.bills.pending} pending)` : ''}
          </button>
        </nav>
      </header>

      {view === 'review' ? (
        <ReviewQueue />
      ) : error && !states.length ? (
        <div className="error-container"><p>{error}</p></div>
      ) : (
        <>
          {loading && !states.length && <div className="loading">Loading…</div>}

          {states.length > 0 && (
            <div className="app-layout">
              <aside className="sidebar">
                {summary && (
                  <Dashboard
                    summary={summary}
                    layer={layer}
                    onLayerChange={setLayer}
                    filter={filter}
                    onFilterChange={setFilter}
                  />
                )}
              </aside>
              <main className="main-content">
                <USMap states={states} layer={layer} onStateClick={setSelectedCode} />
              </main>
            </div>
          )}

          {selectedCode && <StateModal stateCode={selectedCode} onClose={() => setSelectedCode(null)} />}
        </>
      )}
    </div>
  )
}

export default App
