# Changelog

All notable changes to the K-12 AI Legislative Map are recorded here, newest first.
Timestamps are in the project's local time.

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
