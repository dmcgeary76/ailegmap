# Sync implementation (current)

`python -m app.sync.legiscan_sync` — see `--help`. The pipeline, in the order it runs:

1. **Search.** One `getSearch` per jurisdiction with `year=1` (all sessions), paged 50 at a time until
   the index's reported count is satisfied. The query requires an AI term AND an education term in the
   bill *text*. There is deliberately no `NOT (...)` clause: a full-text exclusion for "recognizing" /
   "honoring" removed 44% of Oklahoma's hits, including a signed statute (2026-09-08). `--query` overrides
   the query for diagnosis; `--preview` prints without writing.
2. **Title scorer** (`score_bill`). AI + education term in the title → HIGH; education only → MEDIUM;
   otherwise LOW. Noise (budgets, appropriations, ceremonial, CSAM) and higher-ed-only titles gate to LOW.
   Short terms (`ai`) need a word boundary on both sides — "school aid" is not AI.
3. **Status** (`getBill`) for every bill whose `change_hash` changed. A bill skipped for an unchanged
   hash keeps its stored status; only a status fetched *this run* is written (`_enriched`). Unknown
   status has no stage.
4. **Upsert.** Metadata and automatic classification refresh; `decision` / `reviewed_*` are never
   touched. Stage transitions are logged to `bill_status_changes`.
5. **Carry-over linking.** Same state + number + identical title with a different LegiScan id is one bill
   re-issued in year two of a session: the older copy gets `superseded_by`, a decision carries forward.
6. **`--rescore`** re-runs steps 2, 5 and the text-score fold over stored rows with no network.

**Text-density scorer** (`--score-text`, `app/sync/text_scorer.py`) runs separately: newest text
document per HIGH / MEDIUM / INCLUDED bill via `getBill` → `getBillText`, extracts HTML / PDF / .docx,
counts AI-term hits (whitespace-, hyphen-, ligature- and dropped-space-tolerant), and folds the result
into the confidence: HIGH with no hits → `title_only`; MEDIUM dense (≥3 hits at ≥1/1k words, or ≥2 with
one in a heading) → `dense`; MEDIUM ≤2 hits in definitions or <0.5/1k → `thin_mention`; zero hits →
`no_mention`. Re-runs skip unchanged `text_hash`; `--force-text` re-fetches; `--text-report` prints the
distribution; `--dump-text ST BILL` shows what was extracted.

**Quota.** A full `--all` is ~120 search pages + one `getBill` per changed bill (2,167 on the first
run, far fewer after); `--score-text` is two calls per candidate (~630). Public keys allow 30,000/month.

**Publishing loop:** `sync → --score-text (new bills) → --rescore → seed → export → commit → push`.
The GitHub Action rebuilds the static map on every push to `main`.

Known limits: no `bill_type` from LegiScan yet (resolutions are detected from number/title); LegiScan's
`relevance` is dilution noise under the big OR query and is not used for ranking; territories (GU, PR,
VI) are not in LegiScan at all.
