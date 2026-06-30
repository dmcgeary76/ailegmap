# Data Sync Implementation Guide

Automated pipeline for K-12 AI legislation polling and manual review.

---

## Current implementation (updated 2026-06-30)

The LegiScan sync (`backend/app/sync/legiscan_sync.py`) was substantially reworked. Key behavior:

- **All sessions, not just current.** `getSearch` is called with `year=1` so passed and historical bills are captured (the old default of `year=2` silently dropped them).
- **Relevance-filtered query.** The full-text query requires an AI term **and** an education term, and excludes ceremonial resolutions: a bill must genuinely touch AI in a K-12 context to surface.
- **Confidence scoring.** A client-side scorer reads each bill title and assigns HIGH / MEDIUM / LOW. AI-but-not-education titles (procurement, deepfake/CSAM crime, elections), higher-ed-only bills, and budget/ceremonial noise are scored LOW and held for review rather than auto-included. Matching is word-boundary aware (so "secondary education" does not match inside "postsecondary education").
- **Real status.** `getSearch` does not return a bill's progress, so the sync makes a per-bill `getBill` call (for relevant bills) to populate accurate status (Introduced / Engrossed / Enrolled / Passed / Vetoed / Failed) plus a `stage` for map color-coding.
- **Bill-level review queue.** Every discovered bill is upserted into `bill_review_queue` (model `BillReviewItem`) with its auto-classification and an overridable manual `decision` (PENDING / INCLUDED / EXCLUDED). `effective_included` resolves a manual decision first, else the auto rule (HIGH/MEDIUM in, LOW out). Re-syncs refresh metadata/status but preserve manual decisions; rows are keyed on `(state_code, legiscan_bill_id)` so recycled bill numbers across sessions stay distinct.

CLI:
```bash
python -m app.sync.legiscan_sync --preview --state CA   # ranked results, no DB writes
python -m app.sync.legiscan_sync --state CA             # live sync one state
python -m app.sync.legiscan_sync --all                  # all states + territories
python -m app.sync.legiscan_sync --preview --state TX --no-status  # skip getBill lookups
```

Review API: `GET /api/bills/review`, `GET /api/bills/review/stats`, `POST /api/bills/review/{id}/decision`, `POST /api/bills/review/bulk-decision`. Migration: `002_add_bill_review_queue.py`.

The sections below describe the original review-queue design and remain useful background; where they conflict with the above, the above is current.

---

## Architecture

```
LegiScan API (monthly)
    ↓
legiscan_sync.py (poll for new/updated bills)
    ↓
Flag for review (legislation_updates table)
    ↓
Manual Review Queue API (/api/review/queue)
    ↓
User approves/rejects via API or CLI
    ↓
Apply changes to state_legislation table
    ↓
✅ Live data
```

---

## Step 1: Run Schema Migration

Add new sync tracking fields to database:

```bash
cd backend

# Activate virtual environment
source venv/bin/activate

# Run migration
python -m app.migrations.001_add_sync_tracking upgrade

# Expected output:
# ✅ source_url added
# ✅ last_sync added
# ✅ data_source added
# ✅ bill_status_date added
# ✅ bill_text_url added
# ✅ data_review_queue table created
# ✅ Migration complete!
```

**Verify:**
```bash
psql -U k12_user -d k12_ai_db -c "\d state_legislation" | grep -E "(source_url|last_sync|data_source)"
psql -U k12_user -d k12_ai_db -c "\d data_review_queue"
```

---

## Step 2: Test LegiScan Sync (Dry Run)

Test on a single state without committing changes:

```bash
cd backend

python -m app.sync.legiscan_sync --state CA --dry-run
```

**Expected output:**
```
📡 LegiScan Sync: Single State
======================================================================
State: CA
Dry run: True

  🔍 Searching CA... ✅ (3 found)

======================================================================
📊 SYNC SUMMARY
======================================================================
States searched: 1
Bills found: 3
Bills updated: 0
New bills (flagged): 0
Errors: 0

⚠️  DRY RUN - no changes committed
```

---

## Step 3: Run Live Sync (One State)

Commit changes to database:

```bash
cd backend

python -m app.sync.legiscan_sync --state CA
```

**What happens:**
1. Searches LegiScan for CA K-12 AI bills
2. Updates existing bills (bill_status, bill_url, last_sync)
3. Creates new bills with default stance/maturity
4. Logs all changes to `legislation_updates` table
5. Flags new bills for manual review

---

## Step 4: Review Pending Changes

### Get pending review queue

```bash
curl http://localhost:8000/api/review/queue?status=PENDING
```

**Response:**
```json
[
  {
    "id": 1,
    "state_code": "CA",
    "field_name": "bill_number",
    "current_value": null,
    "proposed_value": "AB 1159",
    "source": "LEGISCAN",
    "status": "PENDING",
    "created_at": "2026-06-25T14:30:00",
    "reviewed_by": null
  },
  ...
]
```

### View queue statistics

```bash
curl http://localhost:8000/api/review/queue/stats
```

### View audit trail for a state

```bash
curl http://localhost:8000/api/review/audit/CA?limit=20
```

---

## Step 5: Approve or Reject Changes

### Approve a change

```bash
curl -X POST http://localhost:8000/api/review/queue/1/approve \
  -H "Content-Type: application/json" \
  -d '{
    "status": "APPROVED",
    "notes": "Verified bill status matches legislature website"
  }'
```

### Reject a change

```bash
curl -X POST http://localhost:8000/api/review/queue/1/reject \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Conflicts with manual research from June 2026"
  }'
```

---

## Step 6: Sync All 50 States (Monthly)

Once tested and happy with single-state sync:

```bash
cd backend

# Dry run first
python -m app.sync.legiscan_sync --all --dry-run

# Then run live
python -m app.sync.legiscan_sync --all
```

**Timeline:**
- ~50 seconds for all states (with rate limiting)
- Updates bill status monthly
- Logs all changes for audit trail

---

## Monitoring & Maintenance

### Check sync status

```bash
curl http://localhost:8000/api/review/queue/stats
```

### View failed syncs

```bash
curl "http://localhost:8000/api/review/queue?status=PENDING&limit=100" | jq '.[] | select(.source == "LEGISCAN")'
```

### Rollback a change

If you reject too many or need to undo approvals:

```sql
-- View rejected items
SELECT * FROM legislation_updates WHERE status = 'REJECTED' ORDER BY created_at DESC LIMIT 10;

-- If you made a mistake, revert status back to PENDING
UPDATE legislation_updates SET status = 'PENDING' WHERE id = 123;
```

### Manual schema rollback

```bash
python -m app.migrations.001_add_sync_tracking downgrade
```

---

## Field Mapping Reference

### LegiScan → Internal Schema

| LegiScan Field | Maps To | Notes |
|---|---|---|
| bill_id | source_url | Stored as API reference |
| bill_number | bill_number | e.g., "AB 1159" |
| title | bill_title | Full bill title |
| status | bill_status | e.g., "Introduced", "In Committee" |
| status_date | bill_status_date | Last status change date |
| url | bill_url | Legislature website link |

### Fields NOT Updated by Sync

- `regulatory_stance` — requires manual classification
- `maturity` — requires timeline analysis
- `guidance_*` — requires separate guidance document parsing
- `teacher_certification_required` — requires bill text reading
- `graduation_requirement` — requires bill text reading

---

## Best Practices

### 1. Monthly Schedule
Run sync once per month to catch new bills and status changes:
```bash
# Add to crontab or scheduler
0 9 1 * * cd /path/to/backend && python -m app.sync.legiscan_sync --all
```

### 2. Review Immediately
After each sync, review new/changed bills:
```bash
curl http://localhost:8000/api/review/queue?status=PENDING | jq length
```

### 3. Classify Stance & Maturity
For new bills, manually read and classify:
- **Regulatory Stance**: PROHIBIT, RESTRICT, REGULATE, SUPPORT, MANDATE, ABSENT
- **Maturity**: NASCENT, IN_PROGRESS, ACTIVE, MATURE

Example workflow:
```bash
# 1. Get pending bills
curl http://localhost:8000/api/review/queue?status=PENDING

# 2. Read the actual bill (visit bill_url)

# 3. Approve with stance classification
curl -X PUT http://localhost:8000/api/states/CA \
  -H "Content-Type: application/json" \
  -d '{
    "regulatory_stance": "RESTRICT",
    "maturity": "IN_PROGRESS",
    "change_reason": "Manual classification after bill text review"
  }'
```

### 4. Audit Trail
Every change is tracked:
```bash
curl http://localhost:8000/api/review/audit/CA | jq '.[] | {field: .field_name, status: .status, reviewed_by: .reviewed_by}'
```

---

## Troubleshooting

### "LegiScan API unreachable"
Check network access:
```bash
curl https://api.legiscan.com/v1/bills/search?state=CA&query=test
```

### "Database connection failed"
Verify PostgreSQL is running:
```bash
brew services list | grep postgresql
psql -U k12_user -d k12_ai_db -c "SELECT 1"
```

### "Migration failed"
Check if columns already exist:
```bash
psql -U k12_user -d k12_ai_db -c "SELECT column_name FROM information_schema.columns WHERE table_name='state_legislation'"
```

### "Review endpoint returns 404"
Make sure backend is running and tables are created:
```bash
curl http://localhost:8000/api/health
psql -U k12_user -d k12_ai_db -c "\d data_review_queue"
```

---

## Next: State Education Guidance Sync

After bill sync is working, next phase builds:
1. Web scraper for state education dept guidance documents
2. PDF parser to extract core principles
3. Semi-automated guidance classification
4. Quarterly sync schedule

See Phase 4 planning in docs/DATA_PIPE_MAPPING.md.
