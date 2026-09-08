"""The bills table is the single source of truth: upserts, decisions, derived headline."""
from app import derive
from app.models.legislation import Bill, BillStatusChange, StateProfile
from app.sync.legiscan_sync import LegiScanSync, rank_bills


def _sync(db):
    return LegiScanSync(db=db, fetch_status=False, api_key="x", sleep=0)


def test_upsert_classifies_and_creates_profile(db, raw_ca):
    s = _sync(db)
    s._ensure_profile("CA")
    s._upsert_bills("CA", rank_bills(raw_ca))
    assert db.query(StateProfile).filter_by(state_code="CA").one().state_name == "California"
    by_num = {b.bill_number: b for b in db.query(Bill).all()}
    assert len(by_num) == 4
    assert by_num["SB1288"].match_confidence == "HIGH" and by_num["SB1288"].effective_included
    assert by_num["AB1064"].bill_status == "Vetoed"
    assert by_num["AB1979"].flag_reason == "review" and not by_num["AB1979"].effective_included
    assert by_num["SB1381"].flag_reason == "noise"
    assert s.stats["new_bills"] == 4


def test_headline_and_stage_follow_decisions(db, raw_ca):
    s = _sync(db)
    s._upsert_bills("CA", rank_bills(raw_ca))
    bills = db.query(Bill).filter_by(state_code="CA").all()
    assert derive.headline_bill(bills).bill_number == "SB1288"   # HIGH + passed
    assert derive.legislation_stage(bills) == "passed"

    # Exclude the passed bill: headline falls back, stage drops to the next best.
    sb = next(b for b in bills if b.bill_number == "SB1288")
    sb.decision = "EXCLUDED"
    db.commit()
    bills = db.query(Bill).filter_by(state_code="CA").all()
    assert derive.headline_bill(bills).bill_number == "AB1064"
    assert derive.legislation_stage(bills) == "failed"           # AB1064 was vetoed

    # Rescue a LOW bill: it appears in the included list.
    ab = next(b for b in bills if b.bill_number == "AB1979")
    ab.decision = "INCLUDED"
    db.commit()
    bills = db.query(Bill).filter_by(state_code="CA").all()
    assert {b.bill_number for b in derive.included_bills(bills)} == {"AB1064", "AB1979"}
    counts = derive.review_counts(bills)
    assert counts == {"total": 4, "included": 2, "pending": 2, "manually_included": 1,
                      "manually_excluded": 1, "held": 2, "resolutions": 0,
                      "by_stage": {"passed": 0, "debated": 0, "introduced": 1, "failed": 1}}


def test_resync_preserves_decisions_and_logs_status_change(db, raw_ca):
    s = _sync(db)
    s._upsert_bills("CA", rank_bills(raw_ca))
    ab = db.query(Bill).filter_by(legiscan_bill_id=103).one()
    ab.decision = "INCLUDED"
    ab.decision_note = "actually about school health AI"
    db.commit()

    # AB1979 advances to Passed, simulating an enriched getBill result
    updated = rank_bills([dict(raw_ca[2], status=4, last_action_date="2025-01-01")])
    updated[0]["_status_label"], updated[0]["_stage"], updated[0]["_enriched"] = "Passed", "passed", True
    s._upsert_bills("CA", updated)
    db.expire_all()

    ab = db.query(Bill).filter_by(legiscan_bill_id=103).one()
    assert ab.bill_status == "Passed" and ab.decision == "INCLUDED"
    assert ab.decision_note == "actually about school health AI"
    assert db.query(Bill).count() == 4
    change = db.query(BillStatusChange).one()
    assert (change.old_stage, change.new_stage) == ("introduced", "passed")
    assert s.stats["status_changes"] == 1


def test_resync_without_enrichment_does_not_clobber_status(db, raw_ca):
    s = _sync(db)
    enriched = rank_bills(raw_ca)
    enriched[0]["_status_label"], enriched[0]["_stage"], enriched[0]["_enriched"] = "Passed", "passed", True
    s._upsert_bills("CA", enriched)
    # A --no-status run, or a bill skipped because its change_hash is unchanged,
    # goes through rank_bills() (which sets _status_label to "Unknown") but not
    # through _enrich(). The stored status must survive. (The old version of
    # this test bypassed rank_bills and so never caught the real-path bug.)
    s._upsert_bills("CA", rank_bills([dict(raw_ca[0], status=None)]))
    db.expire_all()
    assert db.query(Bill).filter_by(legiscan_bill_id=101).one().bill_stage == "passed"


def test_recycled_bill_number_is_a_distinct_row(db, raw_ca):
    s = _sync(db)
    s._upsert_bills("CA", rank_bills(raw_ca))
    s._upsert_bills("CA", rank_bills([
        {"bill_id": 999, "bill_number": "SB1288", "title": "New session: artificial intelligence in public schools.",
         "relevance": 20, "status": 1, "url": "u"},
    ]))
    assert db.query(Bill).filter_by(bill_number="SB1288").count() == 2


def test_known_hashes_skip_unchanged_bills(db, raw_ca):
    s = _sync(db)
    enriched = rank_bills(raw_ca)
    for b in enriched:
        b["_status_label"], b["_stage"] = "Introduced", "introduced"
    s._upsert_bills("CA", enriched)
    hashes = s._known_hashes("CA")
    assert hashes == {101: "h101", 102: "h102", 103: "h103", 104: "h104"}

    calls = []
    s.fetch_status = True
    s.fetch_bill = lambda bid: calls.append(bid) or None
    again = rank_bills(raw_ca)
    again[1]["change_hash"] = "changed"
    s._enrich(again, hashes)
    assert calls == [102]


def test_rescore_reclassifies_stored_rows_without_touching_decisions(db):
    from app.models.legislation import Bill
    from app.sync.legiscan_sync import rescore
    db.add(Bill(state_code="WV", legiscan_bill_id=1, bill_number="HB5205", decision="PENDING",
                bill_title="Requiring the State Board of Education to create model policies on artifical intelligence in schools",
                match_confidence="MEDIUM", flag_reason="review"))
    db.add(Bill(state_code="WV", legiscan_bill_id=2, bill_number="HB1", decision="EXCLUDED",
                bill_title="Relating to bullying in public schools.", match_confidence="MEDIUM", flag_reason=""))
    db.commit()
    r = rescore(db, "WV")
    assert r["rescored"] == 2
    a, b = db.query(Bill).order_by(Bill.legiscan_bill_id).all()
    assert a.match_confidence == "HIGH" and a.flag_reason == "" and "artifical intelligence" in a.matched_ai_terms
    assert b.match_confidence == "MEDIUM" and b.flag_reason == "review" and b.decision == "EXCLUDED"
