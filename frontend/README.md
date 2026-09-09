# Frontend

React 18 + Vite. Real state geometry (d3-geo Albers USA over us-atlas), two color layers, a
local-actions overlay, a state modal, and the bill review queue.

```bash
npm install
npm run dev            # http://localhost:5173, talks to the API on :8000
npm run build:static   # dist/ = map + docs/data.json, no backend needed (GitHub Pages / Vercel)
```

`src/api.js` is the one interface with two implementations: `live` (the FastAPI backend, used by
`npm run dev`) and `static` (reads `data.json`, selected by `VITE_DATA_URL`, used by `build:static`).
Components never know which one they are talking to; the review queue only exists in live mode.

```
src/
├── App.jsx                 # layout, map/review tabs, layer + filter state
├── api.js                  # live vs static data, shared color/label vocabulary
└── components/
    ├── USMap.jsx           # the map: geometry, glyphs, tooltip, NE-state stack
    ├── Dashboard.jsx       # overview stats, layer toggle, filters
    ├── StateModal.jsx      # one state: bills, local actions, guidance profile
    └── ReviewQueue.jsx     # include / exclude bills (live mode only)
```
