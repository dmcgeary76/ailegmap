# K-12 AI Legislative Map

An interactive reference dashboard for tracking artificial intelligence legislation and policy across U.S. states' K-12 public education systems.

Click a state to see the AI legislation governing its K-12 public classrooms, with color-coding for where each bill sits in the legislative process (introduced, debated, passed) and the state's overall regulatory stance.

📄 **Project page & changelog:** see [`docs/index.html`](docs/index.html) (published via GitHub Pages) or [`CHANGELOG.md`](CHANGELOG.md).

## What it does

- **Aggregates K-12 AI legislation** for all 50 states + territories from the [LegiScan API](https://legiscan.com/legiscan), covering passed and historical bills (not just the current session).
- **Filters for relevance.** A bill only counts as K-12-AI legislation if it references both an AI concept *and* a K-12 education concept; everything else (AI procurement, deepfake/CSAM crime bills, higher-ed, budget acts, ceremonial resolutions) is scored down and routed to a review queue rather than shown blindly.
- **Captures real bill status** via per-bill LegiScan `getBill` lookups, so passed / vetoed / introduced is accurate for color-coding.
- **Human-in-the-loop curation.** Every discovered bill lands in a bill-level review queue with an automatic confidence (HIGH/MEDIUM/LOW). A reviewer can include or exclude any bill from the map through a dedicated UI; decisions persist across re-syncs.
- **Sees below the state line.** A curated `local_actions` layer records notable *non-legislative* moves by districts, cities and counties (NYC's PK-8 generative-AI moratorium, LAUSD's device-level block, El Paso ISD's home-grown policy). The direction of each action is the project's sentiment proxy; it rolls up to a per-state "leaning" drawn as a small square on the map.

## Tech stack

- **Frontend:** React 18 + Vite (real-geography US map via d3-geo + us-atlas, two color layers plus glyph overlays, state detail modal, bill review queue). Runs against the API locally, or as a static build that reads `docs/data.json` — see *Publishing the map without a server*.
- **Backend:** Python FastAPI + SQLAlchemy
- **Database:** SQLite (`backend/k12_ai.db`, created automatically — no database server to run)
- **Data sources:** LegiScan API for bills; hand-researched state guidance profiles in `backend/data/profiles/*.json`; hand-curated local actions in `backend/data/local_actions/*.json`

## How the data fits together

There are two independent color layers, and one overlay:

| Layer | Where it comes from | Vocabulary |
|---|---|---|
| **Legislation status** (automatic) | LegiScan bills that a reviewer has included, or that scored HIGH confidence and were never excluded. Derived from the strongest bill: `passed` > `debated` > `introduced` > `failed`. | `legislation_stage` |
| **Regulatory stance** (manual) | `backend/data/profiles/<STATE>.json`, written by a person after reading the state's guidance. Shown only for states marked `RESEARCHED`; everything else is gray "not yet assessed". | `PROHIBIT / RESTRICT / REGULATE / SUPPORT / MANDATE / ABSENT` |
| **Local actions** (manual, overlay) | `backend/data/local_actions/<STATE>.json`: one row per notable district/city/county action, kept small by the inclusion rule in that folder's README. Each action has a `direction` from -2 (prohibit) to +2 (embrace); a state's `local_signal.leaning` is the enrollment- and recency-weighted mean of its *active* actions. Whether an action is active or expired is derived from its dates, never edited. | `restrictive / mixed / permissive`, action types `MORATORIUM / RESTRICT / PERMIT / ADOPT / GUIDANCE / PROCUREMENT` |

A state's `headline_bill` is simply its strongest included bill. Nothing is stored twice: the bill table is the source of truth for legislation, the profile JSON for stance, the local-actions JSON for sub-state activity, and `app/derive.py` computes everything else on read. A gray "not researched" state can carry a red local marker — that contrast (no state policy, biggest district just banned it) is deliberate.

## Quick start

```bash
./setup.sh      # venv, npm install, create SQLite schema, seed the state profiles
./start.sh      # backend on :8000, frontend on :5173
```

Or by hand:
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # (backend/.env.example) add LEGISCAN_API_KEY
python -c "from app.database import init_db; init_db()"
python -m app.seed             # loads backend/data/profiles/*.json
uvicorn app.main:app --reload

cd ../frontend && npm install && npm run dev
```

- Frontend: http://localhost:5173
- API docs (Swagger): http://localhost:8000/docs

### Tests
```bash
cd backend && source venv/bin/activate && pytest
```
The suite runs against a throwaway SQLite database and needs no API key.

### Editing a state's guidance profile
Edit (or create) `backend/data/profiles/<STATE>.json`, set `research_status` to `RESEARCHED`, then run `python -m app.seed`. `python -m app.export` writes the current database back out to JSON if you edited a profile through the API instead.

### Adding a local action
Read the inclusion rule in `backend/data/local_actions/README.md` first (top-5 district in the state, national trade-press coverage, or first-of-its-kind — otherwise it doesn't go in). Add the row to `backend/data/local_actions/<STATE>.json` with at least one source and run `python -m app.seed`. The file replaces that state's rows, so removing a row from the file removes it from the map; to retire an action without losing history set `lifecycle: rescinded`. Weekly skim of K-12 Dive, EdWeek, Chalkbeat and EdSource is enough intake — big-district AI moves are heavily covered.

## Publishing the map without a server

The map half of the app needs no backend: `python -m app.export` writes everything the map shows to
`docs/data.json` (tracked in git), and a static build of the frontend reads that file instead of the API.

```bash
cd backend && source venv/bin/activate && python -m app.export   # refresh docs/data.json
cd ../frontend && npm run build:static                            # -> frontend/dist/ (map + data.json)
```

`frontend/dist/` is a plain folder of files — open it from any static host. The review queue is not in
the static build (there is nowhere to record decisions); reviewing stays local with `./start.sh`.
So the publishing loop is **sync → review → export → commit → push**.

- **GitHub Pages:** `.github/workflows/deploy-pages.yml` builds and deploys on every push to `main`
  (set *Settings → Pages → Source* to "GitHub Actions" once). The map lands at the site root, the
  project page and changelog at `/about/`.
- **Vercel:** import the repo; `vercel.json` already sets the build command and output directory.
- **Anything else** (a VPS behind nginx/Traefik, S3, a USB stick): copy `frontend/dist/` there.

Assets are built with relative paths (`base: './'`), so the same build works at the site root or under a
subpath like `/ailegmap/`.

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
| Education term only (AI somewhere in the body) | MEDIUM | ❌ (held for review) |
| AI only / neither / higher-ed-only / noise | LOW | ❌ (held for review) |

MEDIUM used to auto-include. It stopped on 2026-09-04 after an audit found that 0 of 126 MEDIUM bills had an AI term in the title — they were digital-citizenship, cyberbullying and computer-science-curriculum bills that mention AI once in a definitions section, and they were setting the map color for 21 states. The rule lives in one place, `AUTO_INCLUDE_CONFIDENCE` in `app/models/legislation.py`. The scorer only sees titles; the real fix (scoring AI-term density in the bill *text* via `getBillText`) is on the roadmap.

**Then the text is read.** `python -m app.sync.legiscan_sync --score-text` fetches each HIGH / MEDIUM /
INCLUDED bill's newest text document (`getBill` → `getBillText`; HTML, PDF and .docx are readable, the
rest are flagged `text_unreadable`), counts AI-term hits, notes whether one sits in a section heading
and whether every hit is inside a definition, and folds that into the confidence:

| Title says | Text says | Result |
|---|---|---|
| HIGH | zero AI mentions in a real document | LOW, `title_only` (e.g. "educational materials" false positives) |
| MEDIUM | a heading mentions AI, or 3+ hits | stays MEDIUM, flagged `dense` — review these first |
| MEDIUM | ≤ 2 hits, all inside definitions | LOW, `thin_mention` |
| MEDIUM | anything else | stays MEDIUM, `review` |

Re-runs skip bills whose `text_hash` hasn't changed; `--force-text` re-fetches everything;
`--text-report` prints the distribution without touching the network. The text itself is never stored —
only the counts (`ai_mentions`, `ai_in_heading`, `ai_density`, `definition_only`, `text_words`) — and
`--rescore` re-folds those stored counts, so a text-derived demotion survives a vocabulary change.
Thresholds live at the top of `app/sync/text_scorer.py`.

A manual decision (INCLUDED / EXCLUDED) always overrides the automatic call and survives future syncs.
Decisions live in **`backend/data/decisions.csv`** (tracked in git), keyed by LegiScan bill id: the review
UI writes the file after every decision, and `python -m app.seed` replays it onto the database, so the
SQLite file is a cache and a fresh clone + sync reproduces the curated map. Edit the CSV by hand if you
prefer — it is the source of truth.

**Resolutions never color the map.** HR / SR / HCR / SJR / memorials / Maine "Resolves" (detected from
the bill number, see `is_resolution()` in `models/legislation.py`) stay in a state's bill list with a
*resolution* chip, but an adopted "urging the department to…" is not a law, so `legislation_stage`
skips them and they are never the headline bill when a real bill exists. After changing the vocabulary or gates, `python -m app.sync.legiscan_sync --all --rescore` re-classifies stored rows without any API calls. See [`docs/SYNC_IMPLEMENTATION.md`](docs/SYNC_IMPLEMENTATION.md) for details.

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
- `bills` — every LegiScan result with auto-classification and the reviewer's include/exclude decision (mirrored to `backend/data/decisions.csv`)
- `state_profiles` — hand-researched guidance and stance
- `local_actions` — hand-curated district/city/county actions (`backend/data/local_actions/README.md` documents the fields)

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
- [x] Wire `bill_stage` / `match_confidence` into the map view's color-coding
- [x] `getSearch` pagination for states exceeding the 50-result page
- [x] Real state outlines (d3-geo Albers USA + us-atlas)
- [x] Local (district/city/county) actions layer with derived leaning
- [x] **Text-density scorer:** `--score-text` reads each candidate bill's text and demotes definition-only mentions (`app/sync/text_scorer.py`; design notes in [`docs/TEXT_DENSITY_SCORER.md`](docs/TEXT_DENSITY_SCORER.md))
- [ ] Automated state-education-agency (SEA) guidance scraper
- [ ] `--from-url` helper that drafts a local-action row from an article into a pending queue (only if weekly manual intake gets tedious)

## Notes

This is a personal/internal reference tool. The `LEGISCAN_API_KEY` lives in `backend/.env` and must never be committed.
