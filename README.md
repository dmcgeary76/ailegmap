# K-12 AI Legislative Map

An interactive reference dashboard for tracking artificial intelligence legislation and policy across U.S. states' K-12 public education systems.

Click a state to see the AI legislation governing its K-12 public classrooms, with color-coding for where each bill sits in the legislative process (introduced, debated, passed) and the state's overall regulatory stance.

📄 **Project page & changelog:** see [`docs/index.html`](docs/index.html) (published via GitHub Pages) or [`CHANGELOG.md`](CHANGELOG.md).

## What it does

- **Aggregates K-12 AI legislation** for all 50 states + territories from the [LegiScan API](https://legiscan.com/legiscan), covering passed and historical bills (not just the current session).
- **Filters for relevance.** A bill only counts as K-12-AI legislation if it references both an AI concept *and* a K-12 education concept; everything else (AI procurement, deepfake/CSAM crime bills, higher-ed, budget acts, ceremonial resolutions) is scored down and routed to a review queue rather than shown blindly.
- **Captures real bill status** via per-bill LegiScan `getBill` lookups, so passed / vetoed / introduced is accurate for color-coding.
- **Human-in-the-loop curation.** Every discovered bill lands in a bill-level review queue with an automatic confidence (HIGH/MEDIUM/LOW). A reviewer can include or exclude any bill from the map through a dedicated UI; decisions persist across re-syncs.

## Tech stack

- **Frontend:** React 18 + Vite (interactive US map, state modal, review-queue panel)
- **Backend:** Python FastAPI + SQLAlchemy
- **Database:** PostgreSQL
- **Data source:** LegiScan API (legislation); state education agency guidance (manual today — automated scraper planned)

## Quick start

### Prerequisites
- Python 3.11+, Node 18+, PostgreSQL 14+ (or Docker & Docker Compose)
- A free [LegiScan API key](https://legiscan.com/legiscan)

### Configure secrets
Copy the example env and add your key (this file is gitignored — never commit it):
```bash
cp .env.example backend/.env
# edit backend/.env and set LEGISCAN_API_KEY=your_key
```

### Run (manual)
```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m app.migrations.001_add_sync_tracking upgrade
python -m app.migrations.002_add_bill_review_queue upgrade
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Services:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs

## Syncing legislation

The LegiScan sync searches all sessions, scores each bill for K-12-AI relevance, fetches real status, and populates both the map records and the review queue.

```bash
cd backend && source venv/bin/activate

# Preview ranked results for a state WITHOUT touching the DB (needs only the API key)
python -m app.sync.legiscan_sync --preview --state CA

# Live sync one state, or all states + territories
python -m app.sync.legiscan_sync --state CA
python -m app.sync.legiscan_sync --all

# Faster preview (skip per-bill status lookups)
python -m app.sync.legiscan_sync --preview --state TX --no-status
```

After a live sync, curate results in the **Review Queue** tab of the UI, or via the API:
```bash
curl "http://localhost:8000/api/bills/review/stats?state_code=CA"
curl "http://localhost:8000/api/bills/review?state_code=CA&decision=PENDING"
```

## How relevance works

The sync requires an AI term **and** an education term in the bill text (via a LegiScan boolean full-text query), then a client-side scorer assigns confidence from the bill title:

| Title contains | Confidence | On map by default? |
|---|---|---|
| AI term **and** education term | HIGH | ✅ |
| Education term (AI in body) | MEDIUM | ✅ |
| AI only / neither / higher-ed-only / noise | LOW | ❌ (held for review) |

A manual decision (INCLUDED / EXCLUDED) always overrides the automatic call and survives future syncs. See [`docs/SYNC_IMPLEMENTATION.md`](docs/SYNC_IMPLEMENTATION.md) for details.

## Project structure

```
.
├── backend/                # FastAPI app
│   ├── app/
│   │   ├── models/         # SQLAlchemy models (state_legislation, bill_review_queue, …)
│   │   ├── api/            # routes, review_queue, bill_review
│   │   ├── sync/           # legiscan_sync.py (relevance-filtered LegiScan sync)
│   │   └── migrations/     # 001 sync tracking, 002 bill review queue
│   └── test_bill_review.py # in-memory SQLite test for the review queue
├── frontend/               # React + Vite app
│   └── src/components/     # USMap, StateModal, Dashboard, ReviewQueue
├── docs/                   # Specs, data sources, and the GitHub Pages project page
├── CHANGELOG.md            # Timestamped progress log
└── docker-compose.yml
```

## Data schema

See [`docs/DATA_SCHEMA.md`](docs/DATA_SCHEMA.md). Core entities:
- `state_legislation` — per-state legislation, guidance, and district activity
- `legislation_updates` — field-level change history / audit trail
- `bill_review_queue` — bill-level curation queue with auto-classification and manual include/exclude decisions

## Tests

```bash
cd backend && source venv/bin/activate
python test_bill_review.py     # review-queue behavior (in-memory SQLite)
python test_data_pipes.py      # data-pipeline connectivity checks
```

## Roadmap

- [x] Interactive map, state modal, color-coding scaffolding
- [x] LegiScan sync: multi-year, relevance-filtered, real status
- [x] Bill-level review queue + curation UI
- [ ] Wire `bill_stage` / `match_confidence` into the map view's color-coding
- [ ] Automated state-education-agency (SEA) guidance scraper
- [ ] `getSearch` pagination for states exceeding the 50-result page

## Notes

This is a personal/internal reference tool. The `LEGISCAN_API_KEY` lives in `backend/.env` and must never be committed.
