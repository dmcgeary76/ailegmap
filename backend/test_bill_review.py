#!/usr/bin/env python3
"""
Self-contained test for the bill-level review queue.

Uses an in-memory SQLite database (no Postgres needed) to verify:
  1. The sync upserts discovered bills into bill_review_queue with the right
     confidence / auto-decision / flag.
  2. Manual decisions override the auto classification (rescue a LOW bill,
     demote a HIGH bill).
  3. Re-running the sync refreshes metadata/status but PRESERVES manual decisions
     and does not duplicate rows.
  4. Recycled bill numbers across sessions create distinct rows (keyed on bill_id).

Run from the backend/ directory with the venv active:
    python test_bill_review.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.legislation import BillReviewItem
from app.sync.legiscan_sync import LegiScanSync, rank_bills


def main():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=eng)
    db = sessionmaker(bind=eng)()
    sync = LegiScanSync(db=db, dry_run=False, fetch_status=False, api_key="x")

    raw = [
        {"bill_id": 101, "bill_number": "SB1288", "title": "Public schools: artificial intelligence working group.", "relevance": 41, "status": 4, "url": "u", "last_action_date": "2024-09-01"},
        {"bill_id": 102, "bill_number": "AB1064", "title": "Leading Ethical AI Development (LEAD) for Kids Act.", "relevance": 51, "status": 5, "url": "u", "last_action_date": "2024-09-30"},
        {"bill_id": 103, "bill_number": "AB1979", "title": "Health care services: artificial intelligence.", "relevance": 49, "status": 1, "url": "u", "last_action_date": "2024-02-01"},
        {"bill_id": 104, "bill_number": "SB1381", "title": "Crimes: child pornography.", "relevance": 29, "status": 4, "url": "u", "last_action_date": "2024-08-01"},
    ]
    ranked = rank_bills(raw)
    sync._upsert_review_items("CA", ranked)

    items = {i.bill_number: i for i in db.query(BillReviewItem).all()}
    assert len(items) == 4
    assert items["SB1288"].match_confidence == "HIGH" and items["SB1288"].effective_included
    assert items["AB1064"].bill_status == "Vetoed"
    assert items["AB1979"].match_confidence == "LOW" and not items["AB1979"].effective_included
    assert items["AB1979"].flag_reason == "review"
    assert items["SB1381"].flag_reason == "noise"
    print("1. classification + auto-inclusion: PASS")

    items["AB1979"].decision = "INCLUDED"   # rescue a LOW bill
    items["SB1288"].decision = "EXCLUDED"   # demote a HIGH bill
    db.commit(); db.expire_all()
    items = {i.bill_number: i for i in db.query(BillReviewItem).all()}
    assert items["AB1979"].effective_included is True
    assert items["SB1288"].effective_included is False
    print("2. manual override wins over auto: PASS")

    # Re-sync: AB1979 now Passed; decision must survive, no duplicate
    sync._upsert_review_items("CA", rank_bills([
        {"bill_id": 103, "bill_number": "AB1979", "title": "Health care services: artificial intelligence.", "relevance": 49, "status": 4, "url": "u", "last_action_date": "2025-01-01"},
    ]))
    db.expire_all()
    ab = db.query(BillReviewItem).filter_by(legiscan_bill_id=103).one()
    assert ab.bill_status == "Passed"
    assert ab.decision == "INCLUDED"
    assert db.query(BillReviewItem).count() == 4
    print("3. re-sync refreshes metadata, preserves decision, no dup: PASS")

    # Recycled bill_number across sessions -> distinct rows (keyed on bill_id)
    sync._upsert_review_items("CA", rank_bills([
        {"bill_id": 999, "bill_number": "SB1288", "title": "New session: artificial intelligence in public schools.", "relevance": 20, "status": 1, "url": "u", "last_action_date": "2026-01-01"},
    ]))
    db.expire_all()
    assert db.query(BillReviewItem).filter_by(bill_number="SB1288").count() == 2
    print("4. recycled bill_number creates distinct rows: PASS")

    print("\nALL TESTS PASSED")


if __name__ == "__main__":
    main()
