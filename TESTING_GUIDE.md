# Testing Guide: Data Sync Pipeline

Complete walkthrough to test LegiScan sync + manual review queue locally.

---

## Prerequisites

✅ Backend running (`./start.sh` in another terminal)  
✅ PostgreSQL running (started automatically by setup.sh)  
✅ Database: k12_ai_db with k12_user

**Verify:**
```bash
psql -U k12_user -d k12_ai_db -c "SELECT COUNT(*) FROM state_legislation;"
```

---

## Test 1: Apply Schema Migration

**Goal:** Add sync tracking fields and review queue table.

```bash
cd backend
source venv/bin/activate

# Run migration
python -m app.migrations.001_add_sync_tracking upgrade
```

**Expected output:**
```
Adding sync tracking columns to state_legislation table...
  ✅ source_url added
  ✅ last_sync added
  ✅ data_source added
  ✅ bill_status_date added
  ✅ bill_text_url added

Creating data_review_queue table...
  ✅ data_review_queue table created

Creating indices...
  ✅ review queue status index
  ✅ review queue state index

✅ Migration complete!
```

**Verify:**
```bash
psql -U k12_user -d k12_ai_db -c "\d state_legislation" | grep -E "(source_url|last_sync|data_source|bill_status_date|bill_text_url)"
psql -U k12_user -d k12_ai_db -c "\d data_review_queue"
```

---

## Test 2: Dry-Run LegiScan Sync (Single State)

**Goal:** Test sync without committing to database.

```bash
cd backend
source venv/bin/activate

python -m app.sync.legiscan_sync --state CA --dry-run
```

**Expected output:**
```
📡 LegiScan Sync: Single State
======================================================================
State: CA
Dry run: True

  🔍 Searching CA...
  (Wait 5-10 seconds for API response)
  ✅ (X bills found)

======================================================================
📊 SYNC SUMMARY
======================================================================
States searched: 1
Bills found: X
Bills updated: 0
New bills (flagged): 0
Errors: 0

⚠️  DRY RUN - no changes committed
```

**What happened:**
- Queried LegiScan API for CA K-12 AI bills
- Found bills matching keywords: "artificial intelligence", "AI", "machine learning", etc.
- Would update if not in dry-run mode
- No database changes

---

## Test 3: Live LegiScan Sync (Single State)

**Goal:** Actually commit changes to the database.

```bash
cd backend
source venv/bin/activate

python -m app.sync.legiscan_sync --state CA
```

**Expected output:**
```
📡 LegiScan Sync: Single State
======================================================================
State: CA
Dry run: False

  🔍 Searching CA... ✅ (3 bills found)

======================================================================
📊 SYNC SUMMARY
======================================================================
States searched: 1
Bills found: 3
Bills updated: 2
New bills (flagged): 1
Errors: 0

✅ Sync complete
```

**Verify changes:**
```bash
# Check updated bills
psql -U k12_user -d k12_ai_db -c "SELECT state_code, bill_number, bill_status, last_sync FROM state_legislation WHERE state_code='CA' ORDER BY last_sync DESC LIMIT 5;"

# Check audit trail
psql -U k12_user -d k12_ai_db -c "SELECT state_code, field_name, old_value, new_value, changed_by FROM legislation_updates WHERE state_code='CA' ORDER BY created_at DESC LIMIT 10;"
```

---

## Test 4: Check Manual Review Queue

**Goal:** Verify new bills are flagged for manual review.

### Via API
```bash
curl http://localhost:8000/api/review/queue?status=PENDING

# Expected response:
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
  }
]
```

### Via Database
```bash
psql -U k12_user -d k12_ai_db -c "SELECT id, state_code, field_name, proposed_value, status FROM legislation_updates WHERE status='PENDING' LIMIT 5;"
```

### Get Stats
```bash
curl http://localhost:8000/api/review/queue/stats

# Expected response:
{
  "pending": 1,
  "approved": 0,
  "rejected": 0,
  "total": 1
}
```

---

## Test 5: Approve a Change

**Goal:** Move a pending item through the review workflow.

### Find a pending item
```bash
curl http://localhost:8000/api/review/queue?status=PENDING | jq '.[0]'
```

### Approve it
```bash
curl -X POST http://localhost:8000/api/review/queue/1/approve \
  -H "Content-Type: application/json" \
  -d '{
    "status": "APPROVED",
    "notes": "Verified bill status with CA legislature website"
  }'

# Expected response:
{
  "status": "success",
  "message": "Approved bill_number change for CA",
  "item": {
    "id": 1,
    "status": "APPROVED",
    "reviewed_by": "api_user",
    "reviewed_at": "2026-06-25T14:35:00"
  }
}
```

### Verify approval
```bash
curl http://localhost:8000/api/review/queue?status=APPROVED | jq '.[] | {state: .state_code, field: .field_name, reviewed_by: .reviewed_by}'

# Also check database:
psql -U k12_user -d k12_ai_db -c "SELECT status, reviewed_by, review_notes FROM legislation_updates WHERE id=1;"
```

---

## Test 6: Reject a Change

**Goal:** Test rejection workflow.

### Reject a pending item
```bash
curl -X POST http://localhost:8000/api/review/queue/2/reject \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Conflicts with manual research from June 2026"
  }'

# Expected response:
{
  "status": "success",
  "message": "Rejected bill_title change for CA"
}
```

### Verify rejection
```bash
curl http://localhost:8000/api/review/queue?status=REJECTED | jq '.'

psql -U k12_user -d k12_ai_db -c "SELECT status, review_notes FROM legislation_updates WHERE status='REJECTED';"
```

---

## Test 7: View Audit Trail

**Goal:** See full change history for a state.

```bash
curl http://localhost:8000/api/review/audit/CA | jq '.[] | {field: .field_name, old_value: .old_value, new_value: .new_value, status: .status, changed_by: .changed_by}'

# Database view:
psql -U k12_user -d k12_ai_db -c "SELECT created_at, field_name, old_value, new_value, status, changed_by FROM legislation_updates WHERE state_code='CA' ORDER BY created_at DESC;"
```

---

## Test 8: Sync Multiple States

**Goal:** Test the pipeline across several states.

```bash
cd backend
source venv/bin/activate

# Test 3 states (faster than all 50)
for state in CA HI TX; do
  echo "Syncing $state..."
  python -m app.sync.legiscan_sync --state $state
  sleep 2
done

# Or use built-in multi-state (slower, takes ~50 seconds):
python -m app.sync.legiscan_sync --all
```

**Monitor progress:**
```bash
# In another terminal, watch the review queue grow:
watch -n 5 "curl -s http://localhost:8000/api/review/queue/stats | jq '.'"
```

---

## Test 9: Full Workflow (End-to-End)

Simulate a complete monthly sync cycle:

```bash
#!/bin/bash
# test_full_workflow.sh

echo "📍 Step 1: Run dry-run sync to see what would change"
python -m app.sync.legiscan_sync --state CA --dry-run

echo ""
echo "📍 Step 2: Run actual sync"
python -m app.sync.legiscan_sync --state CA

echo ""
echo "📍 Step 3: Check pending reviews"
curl -s http://localhost:8000/api/review/queue/stats | jq '.'

echo ""
echo "📍 Step 4: List pending items"
curl -s http://localhost:8000/api/review/queue?status=PENDING | jq '.[] | {id: .id, state: .state_code, field: .field_name}'

echo ""
echo "📍 Step 5: Approve first item"
ITEM_ID=$(curl -s http://localhost:8000/api/review/queue?status=PENDING | jq '.[0].id')
curl -X POST http://localhost:8000/api/review/queue/$ITEM_ID/approve \
  -H "Content-Type: application/json" \
  -d '{"status": "APPROVED", "notes": "Verified"}'

echo ""
echo "📍 Step 6: View audit trail"
psql -U k12_user -d k12_ai_db -c "SELECT state_code, field_name, status FROM legislation_updates WHERE state_code='CA' ORDER BY created_at DESC LIMIT 10;"

echo ""
echo "✅ Full workflow complete!"
```

---

## Debugging

### API returns 404 on /api/review/queue
**Problem:** Review queue endpoints not registered.  
**Solution:** Verify backend/app/main.py includes:
```python
from app.api import routes, review_queue
app.include_router(review_queue.router)
```

### LegiScan API times out
**Problem:** Network latency or API down.  
**Solution:** 
```bash
# Test connectivity
curl https://api.legiscan.com/v1/bills/search?state=CA&query=test

# Check if it's a proxy issue (in sandbox/restricted network)
# This is expected in some environments; won't happen on local macOS
```

### "Database connection failed"
**Problem:** PostgreSQL not running or wrong credentials.  
**Solution:**
```bash
brew services list | grep postgresql
psql -U k12_user -d k12_ai_db -c "SELECT 1"
echo $DATABASE_URL  # Check it's set in backend/.env
```

### Migration says "column already exists"
**Problem:** Migration ran before.  
**Solution:**
```bash
# Run idempotent migration (uses IF NOT EXISTS)
python -m app.migrations.001_add_sync_tracking upgrade

# Or check current state:
psql -U k12_user -d k12_ai_db -c "\d state_legislation" | grep source_url
```

---

## Success Criteria

✅ Schema migration creates 5 new fields and review queue table  
✅ LegiScan sync finds bills and flags them  
✅ Review queue shows pending items  
✅ API endpoints approve/reject changes  
✅ Audit trail tracks all changes  
✅ Multiple states can sync without conflicts  
✅ Dry-run shows changes without committing  

Once all tests pass, the pipeline is ready for **monthly scheduling**.

---

## Next: Schedule Monthly Sync

Once tested locally, schedule the sync to run automatically:

```bash
# Add to crontab (runs every 1st of the month at 9am)
0 9 1 * * cd /path/to/AI\ Legislative\ Map/backend && source venv/bin/activate && python -m app.sync.legiscan_sync --all >> /tmp/legiscan_sync.log 2>&1
```

Then manually review pending items in the dashboard each month.
