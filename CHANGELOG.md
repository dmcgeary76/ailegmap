# Changelog

All notable changes to the K-12 AI Legislative Map are recorded here, newest first.
Timestamps are in the project's local time.

---

## 2026-09-04

### Relevance gate: MEDIUM no longer auto-includes
- **Audit.** `score_bill()` only ever sees the title. MEDIUM meant "education word in the title, AI somewhere in the body", and the full-text query's guarantee that AI appears *somewhere* is satisfied by a single mention in a definitions list. Result: 0 of 126 MEDIUM bills had an AI term in the title (by construction), 125 of them were on the map unreviewed — 62% of everything shown — and LegiScan's relevance score couldn't separate them from HIGH (medians 24 vs 26). Texas' MEDIUMs were digital citizenship (SB2787, HB641), cyberbullying (HB1405, SB1445), the SCOPE Act (HB18) and intimate-imagery (SB747) bills; HB18 alone was what colored Texas "passed".
- **Change.** New `AUTO_INCLUDE_CONFIDENCE = ("HIGH",)` in `models/legislation.py` is the single source of the rule; `Bill.effective_included`, the review API's SQL filters/stats, and the sync's `is_k12_ai` gate all read it. MEDIUM rows now carry `flag_reason: review` and wait in the queue like LOW. Map impact: 21 states change — TX/UT/PA/VA/CT/VT downgrade a stage, and AL, AR, FL, GA, KS, MI, MN, MO, NH, NM, NV, RI, SD, TN, WI go gray until a reviewer includes something. Grayer and truer.
- **Typo tolerance.** `AI_TERMS` gains "artifical intelligence", "artificial-intelligence", "artificial intelligance" and "a.i."; the LegiScan query also searches the common misspelling. WV HB5205 ("model policies on ... artifical intelligence") moves MEDIUM → HIGH.
- **`--rescore`.** `python -m app.sync.legiscan_sync --all --rescore` re-runs the title scorer over stored rows with no API calls, so vocabulary/gate changes apply without a full sync. Decisions untouched. Ran it: 1,197 rescored, 129 rows changed (WV's confidence plus the MEDIUM flag_reason backfill).
- 5 new tests (35 total). Next: the text-density scorer described in the README roadmap.

### Local actions layer (v0.3)
- **New `local_actions` table + `backend/data/local_actions/<ST>.json`.** One row per *notable* non-legislative action by a district, city, county or regional body — never one row per district. The folder README carries a written inclusion rule (top-5 district in its state, national trade-press coverage, or first-of-its-kind) so the layer stays at tens of rows nationally.
- **Direction as the sentiment proxy.** Each action has `direction` -2..+2 (prohibit → embrace) plus `action_type`, `applies_to`, `grade_band`, `authority` (a board vote outlives a superintendent memo — worth recording), `lifecycle`, dates, approximate `enrollment`, summary, notes and sources.
- **Derived, not edited.** `derive.py` computes each action's status (proposed / active / expired / rescinded) from its dates and lifecycle, and a per-state `local_signal` (count, active, leaning, score, latest, headline) as the enrollment- and recency-weighted mean direction of *active* actions. A one-year moratorium stops counting the day it ends with no edit. States with no rows read as "no notable local actions", not "neutral".
- **Seeded with three sourced rows:** NYC Public Schools' PK-8 student-facing generative-AI moratorium for 2026-27 (announced 2026-09-02; HS pilots continue; screen-time caps; AI disabled in 38 contracts), LAUSD's district-device block on student gen-AI for 2026-27 (administrator action citing the board's June screen-time vote), and El Paso ISD's home-grown policy in the absence of Texas guidance (carried over from the TX profile note; adoption date unverified and flagged as such).
- **API:** `/api/states` gains `local_signal`; `/api/states/{code}` gains `local_actions`; new `/api/local-actions` list with `state_code` / `status` filters; dashboard summary reports `local_actions` totals and `states_by_local_leaning`. `app.export` includes both.
- **UI:** "Local actions" section in the state modal (placed above the bill list — for a state like NY with 15 included bills it would otherwise be buried), a leaning-colored square on the map, a local headline line in the map tooltip, an "Active local actions" stat, and legend entries.
- **Seed validation.** `python -m app.seed` now fails loudly on a malformed action row (bad enum, direction out of range, unparseable date, unknown field) instead of silently skewing a state's leaning.
- 5 new pytest cases (30 total).

### Real state outlines
- Replaced the labeled-circle markers with actual state geometry: `us-atlas` states-10m TopoJSON projected with `d3-geo`'s Albers USA (Alaska and Hawaii inset automatically). New deps: `d3-geo`, `topojson-client`, `us-atlas` — run `npm install` in `frontend/`.
- Nine small north-eastern states (VT NH MA RI CT NJ DE MD DC) get their labels and glyphs in a stack off the coast with leader lines, the way print atlases do it, so nothing overlaps. DC and the three territories (off-projection) are boxes along the bottom edge.
- Tooltip is now an HTML element that follows the cursor instead of a fixed SVG panel that used to sit on Florida.
- `docs/architecture.mermaid` redrawn for the v0.2/v0.3 model (it still showed PostgreSQL and `state_legislation`).

---

## 2026-09-02

### Rebuilt on one data model (v0.2)
- **SQLite instead of PostgreSQL.** The backend now runs on `backend/k12_ai.db` with zero setup; `init_db()` creates the schema and `python -m app.seed` loads the 54 jurisdiction profiles from `backend/data/profiles/*.json`. Postgres, `docker-compose` as a requirement, and the three hand-rolled migration scripts are gone. `scripts/migrate_from_postgres.py` copies bills and review decisions out of an existing Postgres database if you have one.
- **One source of truth per fact.** The old `state_legislation` row mixed a copied "headline bill", a `legislation_status` that was edited by hand and by the sync, and the manually-researched stance. It is now split: `state_profiles` holds only what a person researched (stance, guidance, maturity, `research_status`), `bills` holds every LegiScan result with its review decision, and `app/derive.py` computes `legislation_stage`, `headline_bill` and the bill counts on every read. Re-syncs can no longer clobber research, and review decisions can no longer disagree with the map.
- **Honest "not yet assessed".** 45 of 54 jurisdictions had never been researched but were displayed as `ABSENT` / "no policy". They now carry `research_status: NOT_RESEARCHED` and render gray on the stance layer. The 9 researched states (AK, CA, HI, MA, RI, TX, GU, PR, VI) kept their content verbatim.
- **Map has two layers.** Color by *Legislation status* (automatic, from included bills) or *Regulatory stance* (manual). Filters, legend and tooltip follow the selected layer; a small amber dot marks states with bills still pending review.
- **State modal lists every included bill** instead of one copied headline, ordered strongest first, with the held/pending count and a pointer to the review tab.
- **API cleanup.** `/api/states` returns the derived shape (`legislation_stage`, `headline_bill`, `bill_counts`, `research_status`); `/api/dashboard/summary` replaces `/api/states/stats` and reports review progress; the duplicate `review_queue.py` router (which crashed on import) is deleted, `bill_review.py` is the only review API. Requesting a state that LegiScan has no data for now 404s instead of inventing a row.
- **Tests.** `backend/tests/` has 25 pytest cases covering derivation, ranking, sync upserts and every endpoint; runs in about a second with no API key.
- **Removed:** `Map.jsx`, `StateMap.jsx` (never mounted), `test_bill_review.py`, `test_data_pipes.py` (Postgres-only), `load_data.sh`, `load_territories.sh`.
- **Still on the roadmap:** real state outlines (the map is still labeled markers at approximate positions), and automated collection of state guidance documents.

---

## 2026-07-02

### Architecture diagram on the project page
- Added a "System architecture" section to `docs/index.html` rendering the LegiScan → sync → PostgreSQL → FastAPI → React data flow as a live Mermaid diagram, matching `docs/architecture.mermaid`.
- Diagram is embedded as Mermaid source (via CDN, rendered client-side) rather than a static image, so `docs/architecture.mermaid` stays the single source of truth — edit one file, both the diagram source and the rendered page update together.
- **Fixed low-contrast diagram:** it originally rendered with Mermaid's light "default" theme inside a white card, but connector lines vanished against the page's dark background wherever that white card didn't render as intended. Switched to Mermaid's dark theme with colors matched to the page palette and a dark panel background for the card, so the diagram is dark-mode-native rather than relying on a light patch surviving inside an otherwise all-dark page.

---

## 2026-07-01

### First full 50-state live sync
- Ran `legiscan_sync.py --all` across all 50 states + 3 territories for the first time. 963 bills found, 194 promoted to HIGH/MEDIUM confidence and shown on the map, 769 held in the review queue.
- Confirmed LegiScan's API does not cover Guam, Puerto Rico, or the US Virgin Islands at all (not a bug — their `getSearch` has no territory support). Territory data will need to come from the separate manual SEA-guidance path, not the bill sync.

### Sync reliability fixes
- **Truncation crash:** `bill_title` was `VARCHAR(255)`/`VARCHAR(500)` and rejected real LegiScan titles that ran longer (e.g. Kansas HB2537's full statutory title), throwing `StringDataRightTruncation`. Widened to `TEXT` on `state_legislation` and `bill_review_queue`.
- **Cascading failures:** `sync_all()` never called `db.rollback()` after a state errored, so one bad insert poisoned the SQLAlchemy session and every subsequent state in that run failed too (one real bug reported as 35). Added a rollback in the error handler so failures stay isolated per state.
- **Sticky primary bug:** a state's headline bill, once set, could never be replaced by a stronger match found on a later sync — e.g. California stayed pinned to an old placeholder bill instead of the actual passed `SB1288`. Added `bill_legiscan_id`, `match_confidence`, and `bill_stage` columns to `state_legislation` (migration `003_widen_titles_and_primary_metadata.py`) so re-syncs can compare and promote the better bill. Retroactively healed CA (`SB1288`, Passed, HIGH), TX (`HB2400`, Introduced, HIGH), RI (`H8345`, Passed, MEDIUM), and other previously-populated states.

### Territory research & seeding
- Confirmed LegiScan has zero coverage of PR, GU, and VI — not a bug, they're simply not in its jurisdiction list, so territories can never come from the bill sync.
- Re-researched GU and VI from scratch rather than trusting old notes. GU turned up new context: a 2025 AI Regulatory Task Force with a University of Guam education subcommittee, plus a non-education-specific GovGuam AI use policy — still no K-12-specific answer. VI unchanged (no formal policy).
- Added `load_territories.sh` to seed PR's already-researched guidance framework (SUPPORT / IN_PROGRESS) and explicit ABSENT records with research notes for GU/VI, so they render with real context on the map instead of empty, unexplained boxes.
- Drafted outreach emails to Guam DOE and VIDE (`docs/territory_outreach_emails.md`) to get a direct K-12-specific answer from each department.

### Review queue usability
- Added "All states/territories" to the Review Queue's state filter so the whole dataset can be viewed at once instead of state-by-state.
- Added a one-click "Needs review only" toggle (surfaces the existing Pending filter, which was previously buried in a dropdown) to cut through the review backlog without losing anything — Included/Excluded bills stay in the data, just out of the way.
- Deliberately did **not** add a way to delete/remove bills from the queue: `_upsert_review_items` re-creates any bill LegiScan still returns on every sync, so a deleted row would just come back as a fresh Pending item and silently erase a prior Exclude decision. Filtering, not deleting, is the right lever here.

### getSearch pagination fix
- LegiScan's `getSearch` caps at 50 results per page; the sync never requested page 2, so six states were silently missing bills beyond page 1 — CA (50 of 89), NJ (50 of 81), HI (50 of 74), MD (50 of 73), NY (50 of 70), and IL (50 of 57), roughly 144 bills across those six that never reached the scorer or the review queue. `search_bills()` now pages through results until the index's reported count is satisfied or a page comes back short.

---

## 2026-06-30

### LegiScan sync — relevance, status, and history
- **Multi-year coverage.** Switched `getSearch` to `year=1` (all sessions) so passed and historical bills are captured. Previously defaulted to the current session only, which dropped passed legislation and left ~33 states looking empty.
- **Relevance-filtered query.** Query now requires an AI term **and** a K-12 education term, and excludes ceremonial resolutions, so unrelated AI bills (procurement, deepfakes, elections) stop surfacing as a state's headline bill.
- **Confidence scoring / fuzzy mapping.** Added a title-based scorer (HIGH/MEDIUM/LOW) with word-boundary matching. Gates out AI-but-not-education titles, higher-ed-only bills, CSAM/criminal bills, and budget/ceremonial noise. Calibrated against live CA/TX results.
- **Real bill status.** Added per-bill `getBill` lookups (relevant bills only) to populate accurate status — Introduced / Engrossed / Enrolled / Passed / Vetoed / Failed — plus a `stage` for color-coding. `getSearch` alone returns no status.
- **Bug fixes.** Dedup now keys on the unique `legiscan_bill_id` (bill numbers recycle across sessions); fixed substring false-match where "secondary education" matched inside "postsecondary education".
- Added `--preview` (no DB) and `--no-status` flags for fast validation.

### Bill-level review queue
- New `bill_review_queue` table + `BillReviewItem` model: one row per discovered bill (any confidence) with auto-classification and an overridable manual decision (PENDING / INCLUDED / EXCLUDED). Manual decisions survive re-syncs.
- New REST API: list (with filters), stats, per-bill decision, and bulk decision endpoints.
- Migration `002_add_bill_review_queue.py`; in-memory SQLite test `test_bill_review.py` (all passing).

### Review queue UI
- New **Review Queue** tab in the app: per-state panel with stats bar, filters (confidence / decision / flag / on-map), status chips, matched-term display, and per-row Include / Exclude / Auto plus bulk select.
- Low-confidence bills sort to the top as the most likely manual-review candidates.

### Documentation & repo
- Rewrote `README.md` for the current architecture; added accuracy update to `docs/SYNC_IMPLEMENTATION.md`.
- Added this changelog, a GitHub Pages project page (`docs/index.html`), and `.gitignore` (excludes `backend/.env` so the LegiScan key is never committed).
- Initialized the git repository and first commit.

---

## Earlier (pre-2026-06-30)

- Project scaffolding: FastAPI backend, React + Vite frontend, PostgreSQL schema.
- Interactive US map with clickable states and a state detail modal.
- Initial LegiScan sync and field-level audit trail (`legislation_updates`).
- Manual research of state education agency (SEA) AI guidance for 12 jurisdictions (CA, HI, MA, RI, AK, AR, CO, LA, NM, OK, TX, PR), captured in `docs/STATE_DATA_SOURCES.md`.
