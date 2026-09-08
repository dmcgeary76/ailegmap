import axios from 'axios'

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = {
  states: (params) => axios.get(`${API_URL}/api/states`, { params }).then((r) => r.data),
  state: (code) => axios.get(`${API_URL}/api/states/${code}`).then((r) => r.data),
  summary: () => axios.get(`${API_URL}/api/dashboard/summary`).then((r) => r.data),
  reviewList: (params) => axios.get(`${API_URL}/api/bills/review`, { params }).then((r) => r.data),
  reviewStats: (params) => axios.get(`${API_URL}/api/bills/review/stats`, { params }).then((r) => r.data),
  decide: (id, body) => axios.post(`${API_URL}/api/bills/review/${id}/decision`, body).then((r) => r.data),
  bulkDecide: (body) => axios.post(`${API_URL}/api/bills/review/bulk-decision`, body).then((r) => r.data),
}

// ---- shared vocabulary ----------------------------------------------------

// Legislation layer: derived from the strongest included bill. Automatic.
export const STAGE_COLORS = {
  passed: '#1d6b3a',
  debated: '#3f87c9',
  introduced: '#8fb7e0',
  failed: '#a89f95',
  none: '#e2e4e0',
}
export const STAGE_LABELS = {
  passed: 'Passed into law',
  debated: 'Advancing (engrossed / enrolled)',
  introduced: 'Introduced',
  failed: 'Failed or vetoed only',
  none: 'No included bills',
}

// Stance layer: manually researched. Only shown where research_status is RESEARCHED.
export const STANCE_COLORS = {
  PROHIBIT: '#dc2626',
  RESTRICT: '#ea580c',
  REGULATE: '#eab308',
  SUPPORT: '#16a34a',
  MANDATE: '#2563eb',
  ABSENT: '#9ca3af',
  UNASSESSED: '#e2e4e0',
}
export const STANCE_LABELS = {
  PROHIBIT: 'Prohibits',
  RESTRICT: 'Restricts',
  REGULATE: 'Regulates',
  SUPPORT: 'Supports',
  MANDATE: 'Mandates',
  ABSENT: 'Researched: no policy',
  UNASSESSED: 'Not yet assessed',
}

export function stanceKey(state) {
  return state.research_status === 'RESEARCHED' ? state.regulatory_stance : 'UNASSESSED'
}
export function stateColor(state, layer) {
  return layer === 'stance'
    ? STANCE_COLORS[stanceKey(state)]
    : STAGE_COLORS[state.legislation_stage || 'none']
}

// Local-action layer: curated district/city/county actions. Overlay, not a
// third color layer -- a gray "not researched" state can still carry a red
// local marker, and that contrast is the point.
export const LEANING_COLORS = {
  restrictive: '#dc2626',
  mixed: '#a16207',
  permissive: '#16a34a',
}
export const LEANING_LABELS = {
  restrictive: 'Local bodies leaning restrictive',
  mixed: 'Local bodies mixed',
  permissive: 'Local bodies leaning permissive',
}
export const ACTION_LABELS = {
  MORATORIUM: 'Moratorium',
  RESTRICT: 'Restriction',
  PERMIT: 'Permits use',
  ADOPT: 'Adoption',
  GUIDANCE: 'Guidance',
  PROCUREMENT: 'Procurement',
}
export const DIRECTION_LABELS = {
  '-2': 'prohibits',
  '-1': 'restricts',
  '0': 'neutral',
  '1': 'encourages',
  '2': 'embraces',
}
