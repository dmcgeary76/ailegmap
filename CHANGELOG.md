# Changelog

All notable changes to the K-12 AI Legislative Map are recorded here, newest first.
Timestamps are in the project's local time.

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
