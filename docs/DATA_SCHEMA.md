# Data schema (v0.3, SQLite)

Five tables. Three are curated or synced inputs; two are bookkeeping. Nothing derived is stored —
`app/derive.py` computes stage, headline, counts and local signal on every read.

## `state_profiles` — manually researched, one row per jurisdiction (54)
Loaded from `backend/data/profiles/<ST>.json` by `python -m app.seed`.

| Column | Notes |
|---|---|
| `state_code`, `state_name` | |
| `research_status` | `NOT_RESEARCHED` / `RESEARCHED` — stance and maturity mean nothing until RESEARCHED; the UI shows "not yet assessed" |
| `guidance_exists`, `guidance_type` (`MANDATORY` `ADVISORY` `PROPOSED` `NONE`), `guidance_issued_by`, `guidance_issued_date`, `guidance_url`, `guidance_core_principles[]` | the state education agency's guidance |
| `regulatory_stance` | `PROHIBIT` `RESTRICT` `REGULATE` `SUPPORT` `MANDATE` `ABSENT` — the stance layer's color |
| `maturity` | `NASCENT` `IN_PROGRESS` `ACTIVE` `MATURE` |
| `key_focus_areas[]`, `unique_context`, `notes`, `sources[]`, `last_updated` | |

## `bills` — everything the LegiScan sync surfaced, one row per LegiScan bill id
| Column | Notes |
|---|---|
| `state_code`, `legiscan_bill_id` (unique together), `bill_number`, `bill_title`, `description`, `subjects[]`, `bill_url`, `bill_text_url` | refreshed each sync |
| `bill_status` (label), `bill_stage` (`introduced` `debated` `passed` `failed`, or NULL when never fetched), `status_date`, `last_action`, `last_action_date`, `change_hash` | from `getBill`; a NULL stage never colors a state |
| `relevance_score`, `match_confidence` (`HIGH` `MEDIUM` `LOW`), `flag_reason`, `matched_ai_terms[]`, `matched_edu_terms[]` | title scorer output; `flag_reason` ∈ `noise` `higher_ed` `review` `dense` `thin_mention` `no_mention` `title_only` `text_unreadable` |
| `text_doc_id`, `text_hash`, `text_mime`, `text_words`, `ai_mentions`, `ai_in_heading`, `ai_density`, `definition_only`, `text_scored_at` | text-density scorer output; the text itself is never stored |
| `superseded_by` | LegiScan id of the newer copy when a two-year session re-issued the same bill; the older copy stays off the map |
| `decision` (`PENDING` `INCLUDED` `EXCLUDED`), `decision_note`, `reviewed_by`, `reviewed_at` | the human call; mirrored to `backend/data/decisions.csv` and replayed by seed |
| `first_seen`, `last_seen` | |

**On the map** (`Bill.effective_included`): `INCLUDED`, or `PENDING` + confidence in `AUTO_INCLUDE_CONFIDENCE` (`HIGH` only) + not superseded.
**Resolutions** (`Bill.is_resolution`, from the bill number or a title beginning "Resolve"/"… Resolution") are listed but never set a state's stage.

## `local_actions` — curated district / city / county actions
Loaded from `backend/data/local_actions/<ST>.json` (the file replaces the state's rows). Fields and the
inclusion rule are documented in that folder's README. `direction` (−2..+2) is the sentiment proxy;
status (proposed / active / expired / rescinded) is derived from `lifecycle` and the dates.

## `sync_runs` — one row per sync invocation (`scope`, `started_at`, `finished_at`, `stats`)
## `bill_status_changes` — a bill moved stage between two syncs (`old_stage` → `new_stage`, `changed_at`)

## `docs/data.json` — the export
`python -m app.export` writes one file carrying what `/api/states`, `/api/states/{code}` and
`/api/dashboard/summary` return, plus `generated_at` / `last_sync`. The static frontend reads only this.
