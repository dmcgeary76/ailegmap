import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import './ReviewQueue.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const STAGE_LABELS = {
  passed: 'Passed',
  debated: 'Debated',
  introduced: 'Introduced',
  failed: 'Failed',
}

// LOW first: low-confidence bills are the most likely manual-review candidates,
// so they float to the top; MEDIUM next, HIGH (usually correct) last.
const CONF_ORDER = { LOW: 0, MEDIUM: 1, HIGH: 2 }

function ReviewQueue() {
  const [stateOptions, setStateOptions] = useState([])
  const [stateCode, setStateCode] = useState('CA')
  const [items, setItems] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [savingIds, setSavingIds] = useState({})
  const [selected, setSelected] = useState(() => new Set())

  // Filters
  const [confidence, setConfidence] = useState('')
  const [decision, setDecision] = useState('')
  const [flagReason, setFlagReason] = useState('')
  const [onMap, setOnMap] = useState('') // '', 'true', 'false'

  // Load the list of states for the selector once.
  useEffect(() => {
    axios
      .get(`${API_URL}/api/states`)
      .then((res) => {
        const opts = (res.data || [])
          .map((s) => ({ code: s.state_code, name: s.state_name }))
          .sort((a, b) => a.name.localeCompare(b.name))
        setStateOptions(opts)
      })
      .catch(() => setStateOptions([]))
  }, [])

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({ state_code: stateCode, limit: '1000' })
      if (confidence) params.append('confidence', confidence)
      if (decision) params.append('decision', decision)
      if (flagReason) params.append('flag_reason', flagReason)
      if (onMap) params.append('included', onMap)

      const [itemsRes, statsRes] = await Promise.all([
        axios.get(`${API_URL}/api/bills/review?${params}`),
        axios.get(`${API_URL}/api/bills/review/stats?state_code=${stateCode}`),
      ])
      const sorted = [...itemsRes.data].sort(
        (a, b) =>
          (CONF_ORDER[a.match_confidence] ?? 9) - (CONF_ORDER[b.match_confidence] ?? 9) ||
          (b.relevance_score || 0) - (a.relevance_score || 0)
      )
      setItems(sorted)
      setStats(statsRes.data)
      setSelected(new Set())
    } catch (err) {
      console.error(err)
      setError('Failed to load review queue. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }, [stateCode, confidence, decision, flagReason, onMap])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const applyDecision = async (id, value) => {
    setSavingIds((p) => ({ ...p, [id]: true }))
    try {
      const res = await axios.post(`${API_URL}/api/bills/review/${id}/decision`, {
        decision: value,
        reviewed_by: 'review_ui',
      })
      setItems((prev) => prev.map((it) => (it.id === id ? res.data : it)))
      // refresh stats (effective_on_map may change)
      const statsRes = await axios.get(`${API_URL}/api/bills/review/stats?state_code=${stateCode}`)
      setStats(statsRes.data)
    } catch (err) {
      console.error(err)
      setError('Failed to save decision.')
    } finally {
      setSavingIds((p) => ({ ...p, [id]: false }))
    }
  }

  const applyBulk = async (value) => {
    const ids = [...selected]
    if (!ids.length) return
    setLoading(true)
    try {
      await axios.post(`${API_URL}/api/bills/review/bulk-decision`, {
        ids,
        decision: value,
        reviewed_by: 'review_ui',
      })
      await fetchData()
    } catch (err) {
      console.error(err)
      setError('Bulk update failed.')
      setLoading(false)
    }
  }

  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    setSelected((prev) =>
      prev.size === items.length ? new Set() : new Set(items.map((i) => i.id))
    )
  }

  return (
    <div className="review-queue">
      <div className="rq-toolbar">
        <div className="rq-control">
          <label>State</label>
          <select value={stateCode} onChange={(e) => setStateCode(e.target.value)}>
            {stateOptions.length === 0 && <option value={stateCode}>{stateCode}</option>}
            {stateOptions.map((s) => (
              <option key={s.code} value={s.code}>
                {s.name} ({s.code})
              </option>
            ))}
          </select>
        </div>

        <div className="rq-control">
          <label>Confidence</label>
          <select value={confidence} onChange={(e) => setConfidence(e.target.value)}>
            <option value="">All</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>
        </div>

        <div className="rq-control">
          <label>Decision</label>
          <select value={decision} onChange={(e) => setDecision(e.target.value)}>
            <option value="">All</option>
            <option value="PENDING">Pending</option>
            <option value="INCLUDED">Included</option>
            <option value="EXCLUDED">Excluded</option>
          </select>
        </div>

        <div className="rq-control">
          <label>Flag</label>
          <select value={flagReason} onChange={(e) => setFlagReason(e.target.value)}>
            <option value="">All</option>
            <option value="review">Review</option>
            <option value="noise">Noise</option>
            <option value="higher_ed">Higher-ed</option>
          </select>
        </div>

        <div className="rq-control">
          <label>On map</label>
          <select value={onMap} onChange={(e) => setOnMap(e.target.value)}>
            <option value="">All</option>
            <option value="true">On map</option>
            <option value="false">Off map</option>
          </select>
        </div>

        <button className="rq-refresh" onClick={fetchData} disabled={loading}>
          ↻ Refresh
        </button>
      </div>

      {stats && (
        <div className="rq-stats">
          <span className="rq-chip total">Total {stats.total}</span>
          <span className="rq-chip high">High {stats.by_confidence.HIGH}</span>
          <span className="rq-chip medium">Medium {stats.by_confidence.MEDIUM}</span>
          <span className="rq-chip low">Low {stats.by_confidence.LOW}</span>
          <span className="rq-divider" />
          <span className="rq-chip onmap">On map {stats.effective_on_map}</span>
          <span className="rq-chip pending">Pending {stats.needs_review}</span>
          <span className="rq-chip included">Included {stats.by_decision.INCLUDED}</span>
          <span className="rq-chip excluded">Excluded {stats.by_decision.EXCLUDED}</span>
        </div>
      )}

      {selected.size > 0 && (
        <div className="rq-bulkbar">
          <span>{selected.size} selected</span>
          <button onClick={() => applyBulk('INCLUDED')}>Include</button>
          <button onClick={() => applyBulk('EXCLUDED')}>Exclude</button>
          <button onClick={() => applyBulk('PENDING')}>Reset</button>
          <button className="rq-clear" onClick={() => setSelected(new Set())}>
            Clear
          </button>
        </div>
      )}

      {error && <div className="rq-error">{error}</div>}
      {loading && <div className="rq-loading">Loading…</div>}

      {!loading && (
        <table className="rq-table">
          <thead>
            <tr>
              <th className="rq-checkcol">
                <input
                  type="checkbox"
                  checked={items.length > 0 && selected.size === items.length}
                  onChange={toggleSelectAll}
                />
              </th>
              <th>Bill</th>
              <th>Title</th>
              <th>Status</th>
              <th>Confidence</th>
              <th>Matched terms</th>
              <th>On map</th>
              <th className="rq-actioncol">Decision</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => {
              const terms = [...(it.matched_ai_terms || []), ...(it.matched_edu_terms || [])]
              return (
                <tr key={it.id} className={it.effective_included ? 'rq-on' : 'rq-off'}>
                  <td className="rq-checkcol">
                    <input
                      type="checkbox"
                      checked={selected.has(it.id)}
                      onChange={() => toggleSelect(it.id)}
                    />
                  </td>
                  <td>
                    <a href={it.bill_url} target="_blank" rel="noreferrer">
                      {it.bill_number}
                    </a>
                  </td>
                  <td className="rq-title" title={it.bill_title}>
                    {it.bill_title}
                  </td>
                  <td>
                    <span className={`rq-stage stage-${it.bill_stage || 'unknown'}`}>
                      {STAGE_LABELS[it.bill_stage] || it.bill_status || '—'}
                    </span>
                  </td>
                  <td>
                    <span className={`rq-conf conf-${(it.match_confidence || '').toLowerCase()}`}>
                      {it.match_confidence}
                    </span>
                    {it.flag_reason ? <span className="rq-flag">{it.flag_reason}</span> : null}
                  </td>
                  <td className="rq-terms">
                    {terms.length ? terms.join(', ') : <span className="rq-muted">—</span>}
                  </td>
                  <td>
                    {it.effective_included ? (
                      <span className="rq-dot on" title="On the map" />
                    ) : (
                      <span className="rq-dot off" title="Off the map" />
                    )}
                  </td>
                  <td className="rq-actioncol">
                    <div className="rq-actions">
                      <button
                        className={it.decision === 'INCLUDED' ? 'active include' : ''}
                        disabled={savingIds[it.id]}
                        onClick={() => applyDecision(it.id, 'INCLUDED')}
                      >
                        Include
                      </button>
                      <button
                        className={it.decision === 'EXCLUDED' ? 'active exclude' : ''}
                        disabled={savingIds[it.id]}
                        onClick={() => applyDecision(it.id, 'EXCLUDED')}
                      >
                        Exclude
                      </button>
                      <button
                        className={it.decision === 'PENDING' ? 'active' : ''}
                        disabled={savingIds[it.id]}
                        onClick={() => applyDecision(it.id, 'PENDING')}
                        title="Defer to automatic classification"
                      >
                        Auto
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
            {items.length === 0 && (
              <tr>
                <td colSpan="8" className="rq-empty">
                  No bills match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default ReviewQueue
