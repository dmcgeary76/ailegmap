# Changelog

All notable changes to the K-12 AI Legislative Map are recorded here, newest first.
Timestamps are in the project's local time.

---

## 2026-09-09

### Docs cleanup; static map cache-busting; Dockerfiles for production shapes
- **Cache bug on the public map.** GitHub Pages serves files with a 10-minute cache and browsers reused the plain `./data.json` URL for far longer, so viewers saw last publish's numbers. The static build now requests `data.json?v=<build id>`; every push rebuilds, so every deploy is a new URL.
- **Removed** the PostgreSQL-era guides (`MACOS_SETUP.md`, `TESTING_GUIDE.md`, `docs/SETUP.md`, `docs/API_SPEC.md`) and the root `.env.example` (Postgres variables; `backend/.env.example` is the real one). Swagger at `/docs` is the API reference.
- **Rewrote** `docs/DATA_SCHEMA.md` and `docs/SYNC_IMPLEMENTATION.md` for the current tables, scorers, flags and publishing loop; `backend/README.md` and `frontend/README.md` are now short module maps.
- **Dockerfiles.** Backend image drops `postgresql-client`; the frontend image is a multi-stage build that serves the static map (with `data.json`) from `nginx:alpine`; `docker-compose.yml` builds those two production shapes instead of running dev servers.
- **`./publish.sh`** runs the whole weekly loop (sync → score text → rescore → seed → export → commit → push); `--no-sync` and `--dry-run` variants.
- **Project page** (`docs/index.html`, published at `/about/`): relevance table now shows the two-stage title + text rule, the run/publish commands match reality, and the changelog carries the September entries.

---

## 2026-09-08

### Local actions: 3 rows → 18 across 10 states
- Researched under the inclusion rule (top-5 district in its state, national trade-press coverage, or first-of-its-kind), each row sourced and dated, approximate enrollment for weighting. New: **FL** Miami-Dade (Gemini to ~100k high-schoolers, 2025, +2), Broward (K-5 no student AI, 6-12 teacher-directed, 2026-27, −1), Orange County (first AI policy, 2026-07-28, +1), Hillsborough (Policy 2130 + implementation guide, 2025-06, +1); **VA** Fairfax (elementary gen-AI prohibited, device limits, board 2026-07-16, −1); **TX** Houston ISD (nine AI-focused "Future 2" campuses + Alpha School pilots, 2026-27, +2), Dallas ISD (AI playbook in grading/conduct regs, 2025-06-24, +1); **GA** Gwinnett (district-wide K-12 guidance, 2024-07-23, +1); **IL** Chicago (AI Guidebook, 2024-08, +1 — with the 2026 board-candidate moratorium pledge noted); **NC** Charlotte-Mecklenburg (board policy, 2025-10-28, +1), Wake County (draft, lifecycle *proposed*); **PA** Philadelphia (PASS educator training, 2025-03, +1, staff-facing); **AZ** Tucson Unified (board tie blocks expansion beyond high school, 2026-05-28, −1). Two history rows with lifecycle *rescinded* so they list but never count: NYC's 2023 ChatGPT ban and reversal, and LAUSD's $6M "Ed" chatbot (Mar–Jun 2024).
- Rollup: 15 active actions; leaning restrictive in CA, NY, VA, AZ; permissive in FL, GA, IL, NC, PA, TX. The contrast the layer was built for is now visible: New York and California are gray on the legislation layer and red on the local layer.
- Still thin: Broward's row rests on secondary coverage of CBS Miami / Axios (verify against browardschools.ai); Wake flips to *adopted* when the board votes; nothing yet for NV (Clark County), MD (Montgomery), WA (Seattle, which has guidance but no dated action), CO, MA, OH.

### Text scorer calibrated on 315 real documents; 44 dense MEDIUMs reviewed
- **Three runs, three extraction lessons.** (1) Iowa's "HTML" is one word per line and Iowa/Louisiana PDFs wrap phrases across margin line numbers, so phrase patterns now allow whitespace, hyphens or stray numbers between words — the five "title_only" HIGH demotions from run 1 were all this. (2) Missouri's PDFs drop inter-word spaces ("ofartificial intelligence"), so multi-character terms match with no word boundaries at all; only `ai` keeps both. (3) PDF ligatures (ﬁ), soft hyphens and end-of-line hyphenation are normalised before matching.
- **Thresholds from the distribution.** A heading hit alone made one bill in three "dense" because every wrapped PDF line is short; headings now need a Section/Article lead or ALL CAPS, and a heading counts only with ≥2 hits. Dense needs ≥3 hits at ≥1 per 1,000 words (Connecticut's 84k-word bond bill had 11 hits); thin also covers ≤2 hits under 0.5/1k; MEDIUM with zero hits → `no_mention`. Ohio HB455 (167k words, 0 hits in the enrolled text — LegiScan matched an earlier version) is the intended outcome, not a miss.
- **Final distribution (315 scored):** HIGH 97 · MEDIUM dense 45 / review 75 · LOW thin 57 / no_mention 22 / noise 4 / higher_ed 1. 217 MEDIUMs became 120, and 45 of those were reviewed by title + counts: 35 included, 9 excluded, 1 left for David (PA HB1505, Act 20 of 2026 — an omnibus school code with an AI section heading; if substantive, Pennsylvania is a "passed" state). Notable includes: **UT HB0273 Classroom Technology Amendments — passed 2026, 55 AI hits — Utah joins the passed states**; CA AB1159 / AB2071 / AB2298 enrolled 2026; KY SB52; PA HB2375 (AI instructors in charters); IL SB0416. `decisions.csv` at 157 rows.
- **Resolutions by title.** Rhode Island numbers House resolutions like bills (H8345, "HOUSE RESOLUTION CREATING…"); `is_resolution()` now also reads a title that begins "Resolve" / "… Resolution". 16 more rows flagged, all correct on inspection; RI drops back out of "passed".
- Map after this pass: passed CA, ID, IL, MD, OK, UT, VA; 119 bills on the map, 10 of them resolutions.

### Text-density scorer (the roadmap item)
- New `app/sync/text_scorer.py`: `--score-text` fetches each HIGH / MEDIUM / INCLUDED bill's newest text (`getBill` → `getBillText`), extracts HTML / PDF (`pypdf`) / .docx, counts AI-term hits (same vocabulary as the title scorer, both-boundary matching for short terms, overlapping hits de-duplicated), detects a hit in a section heading, and checks whether every hit sits within 200 chars of a definition cue. Stored on `bills` as counts only — `text_words`, `ai_mentions`, `ai_in_heading`, `ai_density`, `definition_only`, plus `text_doc_id` / `text_hash` / `text_mime` / `text_scored_at`; the text itself is never kept.
- **Rules (`combine`)**: HIGH with zero hits in a ≥200-word document → LOW `title_only`; MEDIUM with a heading hit or ≥3 hits → MEDIUM `dense` (review these first); MEDIUM with ≤2 hits all in definitions → LOW `thin_mention`; unreadable formats (WordPerfect, .doc, RTF) → `text_unreadable`, confidence unchanged. Title-only `noise` / `higher_ed` gates are never overridden. Thresholds at the top of the module — first cut, to be tuned from `--text-report`.
- `--rescore` now re-folds the stored text columns, so a text-derived demotion survives a vocabulary change. `--force-text` re-fetches regardless of hash; already-scored bills stay candidates so a changed document is re-read.
- Review queue shows `text: N hits / M words · in heading · definitions only`, a carry-over-duplicate note, and the new flags in the flag filter.
- 7 new tests (52 total) incl. an end-to-end run against a stubbed LegiScan. `pypdf` added to requirements.

### First full re-sync after the query fix — and two more sync bugs it exposed
- **Numbers.** 2,206 bills found across 50 states + DC (was 1,197); 991 new; 2,167 `getBill` calls, 0 errors, 23 minutes. DC has rows for the first time (42). LegiScan `getSearch` counts: CA 200, NY 150, VA 142, NJ 122, HI 118 — CA's round 200 is being checked for a result cap.
- **Bug: the title scorer's "ai" term matched "aid".** `_matched_terms` enforced only a left word boundary (so "school" matches "schools"), which made `ai` match "school **ai**d", "aims", "aircraft". Seven Michigan school-aid appropriations bills and nine New York budget bills scored HIGH and went straight onto the map. Fixed: terms of three letters or fewer require a right boundary too. Noise vocabulary also gains `appropriations`, `honor`, `inaugural year` and `necessary to implement the state`. `--rescore` moved 125 rows.
- **Bug: a re-sync erased statuses.** `rank_bills()` always sets `_status_label` (to "Unknown" — `getSearch` carries no status), and `_upsert_bills` treated the presence of that key as "status fetched this run". So every bill whose unchanged `change_hash` let the sync skip `getBill` had its real status overwritten with Unknown. This is why 995 bills sat at "Unknown" before today, and why Oklahoma's 39 bills (synced twice in a row) lost the statuses the first run had just fetched. Fixed with an explicit `_enriched` flag; the existing test that should have caught it bypassed `rank_bills()` and has been made realistic.
- **Audit of the 39 new HIGH bills.** After the scorer fix, 21 remained: 20 included (notably VA HB1186 / SB394 enacted 2026 — Virginia joins the "passed" states; IL SB2909 now shows Passed; OK SB1734 finally present; DC B26-0491; NY's humanoid-robot bills A11662 / S10671), 1 excluded (IA HSB609, renumbered as HF2528). `decisions.csv` is at 113 rows. PA HB1505 (Act 20 of 2026, an omnibus school code) is now LOW/noise via `omnibus`; if its AI section turns out substantive, include it by hand.
- Map after this pass: passed CA, ID, IL, MD, VA (+OK once its status is refetched); 84 bills on the map; 56 carry-over duplicates linked.

### Sync correctness: carry-over duplicates, honest "Unknown", bad dates
- **Carry-over duplicates.** LegiScan issues a new bill id when a two-year session rolls into its second year, so the same bill appears twice (27 groups already in the DB, 15 of them Hawaii; identical titles). New `bills.superseded_by` column: after each state upsert, `link_carryovers()` points every older copy at the newest id, carries a reviewer's decision forward onto the new copy, and keeps the old one off the map (`effective_included` and the review API's on-map filter both respect it). A reused number with a different title (CA AB1651, 2022 vs 2026) is left alone. `--rescore` runs it too, with no network.
- **"Unknown" no longer means "Introduced".** `map_status(None)` used to return stage `introduced`, so a bill whose status was never fetched could color a state. It now returns no stage; `--rescore` clears the stage on stored Unknown rows.
- **`0000-00-00` dates** are stored as empty (TX HB1709 had one).
- `init_db()` now adds missing columns to an existing SQLite file (`create_all` only creates tables), so no manual migration.
- 3 new tests (43 total).

### Sync recall bug: the ceremonial-resolution NOT clause was hiding real statutes
- **Found via OK SB 1734.** A signed K-12 AI statute with "artificial intelligence" in its title never reached the bills table. Bisected with the new `--query` flag: LegiScan indexes the bill (`SB1734` → rel 99; `"artificial intelligence" AND school` → #1 at rel 100); our production query returned 22 Oklahoma bills without it; the same query minus its `NOT (congratulating OR commending OR recognizing OR honoring OR commemorating)` tail returned 39 *with* it; and `"Responsible Technology in Schools" AND (those words)` returned the bill — its text uses one of them.
- **Root cause.** The NOT clause is a full-text exclusion. It was meant to drop ceremonial resolutions, but any statute whose text says "recognizing" or "honoring" anywhere was silently excluded: 17 of 39 Oklahoma hits (44%). Assume a similar share nationally.
- **Fix.** NOT clause removed from `SEARCH_QUERY`. Ceremonial noise is already handled downstream by the title scorer's `NOISE_TERMS` and by `is_resolution()`. A full re-sync is required and will find substantially more bills; all of them land in the review queue under the usual HIGH-only auto-include rule.
- **Also observed:** LegiScan's relevance scores under the big OR query are 6–21 versus 60–100 under a two-term query — dilution, not signal. Don't lean on `relevance_score` for ranking. And several bills come back twice under one number with different LegiScan ids (OK SB224, HB1983, HB2371, HB1916, HB2016) — looks like separate 2025/2026 records in a two-year session; dedup is by id, so both are kept. Worth a look.
- New `--query` override on `legiscan_sync` for this kind of diagnosis.

### Five more researched profiles: AR, CO, LA, NM, OK (9 → 14 of 54)
- Drafted from current agency pages, statutes and trackers, reviewed and approved by David the same day. **OK** REGULATE / ACTIVE — the Responsible Technology in Schools Act (SB 1734, signed 2026-05-12, effective 2026-07-01) mandates board-approved district AI policies before 2027-28, bars AI as the primary basis for grading/discipline/promotion, and gives parents an opt-out. **LA** SUPPORT / ACTIVE (LDOE advisory guidance, 2024-08-28; HB 119 Ivy Daniels Act adds a grade-6+ instruction mandate on AI-image offenses). **NM** SUPPORT / IN_PROGRESS (PED guidance 1.0 signed 2025-04-29; LESC still pushing for comprehensive policy). **CO** SUPPORT / ACTIVE (Colorado Education Initiative roadmap, Aug 2024, linked by CDE — nonprofit-authored, noted as such). **AR** ABSENT / NASCENT (no SEA guidance; governor's AI working group reports cover state government only).
- Also updated `docs/STATE_DATA_SOURCES.md`-era claims: the OK note undersold SB 1734; the AR "vendor data agreements" claim had no source and was dropped.
- **Sync recall bug found:** OK SB 1734 — a signed statute with "artificial intelligence" in its title — is not in the bills table after the June 30 sync. Investigate before the next full sync.
- `docs/data.json` regenerated: 14 researched, stance counts SUPPORT 7 / ABSENT 4 / PROHIBIT 1 / REGULATE 1 / MANDATE 1.

### HIGH-bill audit: every auto-included bill now has a human-readable decision
- **Why.** 75 HIGH bills were coloring 25 states with nobody having looked at them. Among the ones painting states "Passed into law": WY HB0102 (a deepfake/exploitative-imagery crime statute), ME LD109 (a Resolve about the Arts Commission and AI copyright), NY S08831 (automated employment-decision tools for public employers — school districts appear only as employers), plus two adopted resolutions (HI HR40, LA HR249) that "urge" a department and are not laws.
- **Decisions.** All 75 reviewed by title/description. 14 excluded (CT HB06889, ME LD109, NJ A2616/A4821/A5034, NY A04550/A07838/A09106/S08484/A09487/S08831, PA HB2314, WA SB6082, WY HB0102), 61 included, each with a one-line note; borderline keeps flagged in the note (NY S10049 DASA/cyberbullying, NY A08947 internet-safety curriculum, VT H0863 marked *verify*). Reviewer is recorded as `claude-audit-2026-09-08` so the calls are distinguishable from David's — flip any row in the CSV.
- **Map impact.** "Passed into law" goes from 8 states to 3 (CA, ID, MD). WY, ME, PA, WA go gray. 64 bills on the map (was 78); 1,105 pending (was 1,180).
- **Resolutions never color the map.** New `is_resolution()` (bill-number prefix: HR/SR/HCR/SCR/HJR/SJR/ACR/AJR, memorials HM/SM/HJM, Nebraska LR; Maine LDs whose title begins "Resolve"). 75 of 1,197 stored bills match, all sensible on inspection. `derive.legislation_stage()` and `by_stage` skip them; the headline bill prefers a real bill; `BillBrief.is_resolution` drives a *resolution* chip in the modal, a note under "Bills on the map", and "(resolution)" in the map tooltip. Proper `bill_type` from `getBill` can replace the heuristic when the text scorer adds a column.
- **Decisions live in git.** New `backend/data/decisions.csv` (state, bill number, LegiScan id, decision, reviewer, timestamp, note) — 92 rows: the 17 existing UI decisions plus the audit. `app/decisions.py` dumps and replays it; `python -m app.seed` now replays it after profiles and local actions; the review API writes the file after every decision. The SQLite file is now a cache: clone + sync + seed reproduces the curated map. **Run `python -m app.seed` locally to apply the audit to your DB.**
- 5 new tests (40 total). `docs/data.json` regenerated.

### Static-data mode: the map no longer needs a server
- **One interface, two data sources.** `frontend/src/api.js` now has a `static` implementation next to the live one. With `VITE_DATA_URL` set (the `build:static` script sets it to `./data.json`) the app loads the export once and serves `states()` (with the same `stance` / `legislation_stage` filters the API accepts), `state(code)` and `summary()` from it. Components don't know which mode they're in. The review-queue calls reject with a clear message; the Review tab is hidden and the header shows "Data as of …" plus the pending count instead.
- **Export carries the whole read model.** `docs/data.json` now includes the dashboard `summary` (the endpoint's builder was extracted to `build_dashboard_summary()` in `routes.py` so the two can't drift) and each state's `headline_bill`. Regenerated: 54 jurisdictions, 78 included bills, 128 KB.
- **Deployable anywhere.** `vite.config.js` sets `base: './'` so the same build works at a site root (Vercel) or under `/ailegmap/` (GitHub Pages). `npm run build:static` produces `frontend/dist/` = app + `data.json` (~500 KB total). Verified headless: zero requests to `:8000`, one to `data.json`, filters and the state modal work, no console errors.
- **Deploy plumbing.** `.github/workflows/deploy-pages.yml` builds on push to `main` and publishes to Pages with the map at the root and `docs/` at `/about/` (requires switching the Pages source to "GitHub Actions" once). `vercel.json` sets the build command and output directory for a Vercel import.
- **Housekeeping (earlier today).** First commit since July 2 — a stale `.git/HEAD.lock` from that day had been blocking commits. `.gitignore` now covers `*.db-wal`, `*.db-shm`, `.fuse_hidden*`, and the session-screenshot folder; `docs/data.json` is tracked.
- Publishing loop is now: **sync → review → export → commit → push.** Still to do: the HIGH-bill audit (WY and ME are green on the strength of a deepfake bill and an arts-commission resolve), resolution-aware stage, the five missing profiles, and the text-density scorer.

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
