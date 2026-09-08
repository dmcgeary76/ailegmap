# Text-density scorer — design notes

> **Built 2026-09-08** as `backend/app/sync/text_scorer.py`, run with
> `python -m app.sync.legiscan_sync --score-text`. The notes below are the original scope;
> thresholds now live at the top of that module and the README documents the rules.

**Problem.** `score_bill()` sees only the title. A bill clears the LegiScan full-text query by
mentioning an AI term *once, anywhere* — so digital-citizenship, cyberbullying and CS-curriculum
bills that define "artificial intelligence" in a definitions section score MEDIUM alongside bills
that are actually about AI. Since 2026-09-04 MEDIUM no longer auto-includes, which is honest but
means every real MEDIUM has to be promoted by hand. The fix is to look at the text.

**Signal.** For each bill, fetch the latest text and compute:

| Feature | Meaning |
|---|---|
| `ai_mentions` | count of AI-term hits in the body (word-boundary, same `AI_TERMS` list) |
| `ai_in_heading` | an AI term appears in a section heading / caption / short title line |
| `ai_density` | `ai_mentions` per 1,000 words |
| `definition_only` | every hit sits within N chars of "means" / "definition" / "as used in" |

**Rule (first cut, tune against the 126 MEDIUM rows):**

- `ai_in_heading` **or** `ai_mentions >= 3` → keep MEDIUM (and auto-include MEDIUM+dense? decide after
  looking at the distribution; default no — keep the map HIGH-only until the numbers earn it)
- `ai_mentions <= 2` and `definition_only` → demote to LOW, `flag_reason: thin_mention`
- HIGH bills also get scored; a HIGH with `ai_mentions == 0` in the body is a title false-positive
  (e.g. KS HB2537's "educational materials") → demote to LOW, `flag_reason: title_only`

Store on `bills`: `text_doc_id`, `text_hash` (LegiScan's MD5), `ai_mentions`, `ai_in_heading`,
`ai_density`, `text_scored_at`. Never store the text itself.

**API cost.** `getBill` already returns a `texts[]` array (`doc_id`, `type`, `mime`, `text_size`,
`date`); take the newest. `getBillText(id=doc_id)` returns the document base64-encoded with `mime_id`
(1 HTML, 2 PDF, 3 WordPerfect, 4 .doc, 5 RTF, 6 .docx) and `text_hash`. One call per bill, skipped
when `change_hash` is unchanged or `text_hash` matches what we stored. First run: ~200 calls
(76 HIGH + 126 MEDIUM); LOW is not worth the quota. Public keys allow 30,000 queries/month, so this
is noise. Rate-limit with the existing `sleep`.

**Extraction.** HTML → strip tags (stdlib `html.parser`). PDF → `pdftotext` (poppler) or `pypdf`
(`pip install pypdf`). .docx → `python-docx` or unzip + XML. WordPerfect/.doc/RTF → skip with
`flag_reason: text_unreadable` and leave the title score in place; if that bucket is more than a
handful, revisit. Cap decoded text at ~2 MB.

**Wiring.** New module `app/sync/text_scorer.py` with a pure `score_text(text: str) -> dict` (unit
tested on fixture snippets) and a `--score-text [--state XX]` mode on `legiscan_sync` that reads
`texts[]` off a fresh `getBill`, fetches, scores, and writes the columns. `score_bill()` stays
title-only; a second function `combine(title_score, text_score)` decides the final confidence so
each layer stays testable on its own.

**Effort.** Half a day: ~150 lines of Python, one migration-free `init_db()` (SQLite adds columns
via `create_all` only for new tables — add the columns with a one-off `ALTER TABLE` script or
recreate from the export), and an afternoon of reading the 126 MEDIUMs against the numbers to
set the thresholds. Calibrate before trusting: print `ai_mentions` / `definition_only` for the
Texas set (SB2787, HB641, HB1405, SB1445, HB18, SB747, HB4390) and for UT HB0273 "Classroom
Technology Amendments" and MO HB2612's ed-tech advisory council, which are the plausible keepers.
