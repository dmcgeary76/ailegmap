"""Resolutions never color the map; decisions round-trip through data/decisions.csv."""
from datetime import datetime

from app import derive, decisions
from app.models.legislation import Bill, is_resolution


def _bill(state, number, title, stage, conf="HIGH", decision="PENDING", bid=None):
    return Bill(state_code=state, legiscan_bill_id=bid or abs(hash((state, number))) % 10**7,
                bill_number=number, bill_title=title, bill_stage=stage,
                bill_status=stage.title(), match_confidence=conf, decision=decision)


def test_is_resolution_by_number_and_maine_title():
    assert is_resolution("HR40")
    assert is_resolution("HCR44")
    assert is_resolution("SJR12")
    assert is_resolution("ACR51")
    assert is_resolution("HJM9")
    assert is_resolution("LR233")
    assert is_resolution("LD109", "Resolve, Directing the Maine Arts Commission to Study...")
    assert not is_resolution("LD1234", "An Act to Establish AI Guidance")
    assert not is_resolution("HB0102")
    assert not is_resolution("S08831")
    assert not is_resolution("H8345")
    assert not is_resolution("HF2153")
    assert not is_resolution("AB2876")
    assert not is_resolution("SSB1002")


def test_adopted_resolution_does_not_set_stage():
    hr = _bill("HI", "HR40", "Urging the Department of Education...", "passed")
    hb = _bill("HI", "HB1887", "Relating to AI literacy education", "introduced")
    assert derive.legislation_stage([hr, hb]) == "introduced"
    assert derive.legislation_stage([hr]) is None
    counts = derive.review_counts([hr, hb])
    assert counts["included"] == 2
    assert counts["resolutions"] == 1
    assert counts["by_stage"] == {"passed": 0, "debated": 0, "introduced": 1, "failed": 0}
    # still listed, but a real bill is the headline even when the resolution "passed"
    assert [b.bill_number for b in derive.included_bills([hr, hb])] == ["HB1887", "HR40"]
    assert derive.headline_bill([hr, hb]).bill_number == "HB1887"


def test_decisions_round_trip(db, tmp_path):
    a = _bill("WY", "HB0102", "Protecting kids from deepfakes", "passed", bid=1)
    b = _bill("MD", "SB720", "AI Ready Schools Act", "passed", bid=2)
    c = _bill("TX", "HB2400", "Prohibition on AI for classroom instruction", "introduced", bid=3)
    db.add_all([a, b, c]); db.commit()

    a.decision, a.decision_note, a.reviewed_by, a.reviewed_at = "EXCLUDED", "criminal law, not K-12 policy", "audit", datetime(2026, 9, 8, 12, 0)
    b.decision, b.reviewed_by = "INCLUDED", "audit"
    db.commit()

    path = tmp_path / "decisions.csv"
    assert decisions.dump(db, path) == 2
    text = path.read_text()
    assert "WY,HB0102,1,EXCLUDED,audit,2026-09-08T12:00:00,\"criminal law, not K-12 policy\"" in text
    assert "TX" not in text  # PENDING rows are not written

    # Wipe the DB-side decisions and replay from the file
    a.decision = b.decision = "PENDING"; a.decision_note = a.reviewed_by = None; a.reviewed_at = None
    db.commit()
    assert decisions.apply(db, path) == 2
    db.refresh(a); db.refresh(b)
    assert a.decision == "EXCLUDED" and a.decision_note == "criminal law, not K-12 policy"
    assert a.reviewed_at == datetime(2026, 9, 8, 12, 0)
    assert b.decision == "INCLUDED"
    assert decisions.apply(db, path) == 0  # idempotent


def test_decisions_file_validated(tmp_path):
    p = tmp_path / "decisions.csv"
    p.write_text("state_code,bill_number,legiscan_bill_id,decision,reviewed_by,reviewed_at,note\nWY,HB0102,1,MAYBE,,,\n")
    try:
        decisions.read(p)
    except ValueError as e:
        assert "line 2" in str(e)
    else:
        raise AssertionError("bad decision value should fail loudly")


def test_review_api_writes_decisions_file(client, db):
    from app import decisions as d
    b = _bill("WY", "HB0102", "Protecting kids from deepfakes", "passed", bid=77)
    db.add(b); db.commit()
    r = client.post(f"/api/bills/review/{b.id}/decision",
                    json={"decision": "EXCLUDED", "note": "not K-12", "reviewed_by": "t"})
    assert r.status_code == 200
    assert d.DECISIONS_PATH.exists()
    assert "WY,HB0102,77,EXCLUDED,t," in d.DECISIONS_PATH.read_text()


def test_carryover_duplicates_are_linked_and_decision_carries(db):
    from app.sync.legiscan_sync import link_carryovers
    old = _bill("HI", "HB1887", "Relating To Artificial Intelligence Literacy Education.", "introduced", bid=100)
    new = _bill("HI", "HB1887", "Relating To Artificial Intelligence Literacy Education.", "debated", bid=200)
    other = _bill("HI", "HB1887", "A completely different bill reusing the number", "introduced", bid=300)
    old.decision, old.reviewed_by = "EXCLUDED", "david"
    db.add_all([old, new, other]); db.commit()

    assert link_carryovers(db, "HI") == 1
    db.refresh(old); db.refresh(new); db.refresh(other)
    assert old.superseded_by == 200
    assert new.superseded_by is None and other.superseded_by is None
    assert new.decision == "EXCLUDED" and new.reviewed_by == "david"   # carried forward
    assert not old.effective_included
    assert link_carryovers(db, "HI") == 0                                 # idempotent

    # the superseded copy is not counted on the map
    counts = derive.review_counts([old, new, other])
    assert counts["included"] == 1   # only `other` (HIGH, pending, not superseded)


def test_unknown_status_has_no_stage():
    from app.sync.legiscan_sync import map_status, _clean_date
    assert map_status(None) == ("Unknown", None)
    assert map_status(4)[1] == "passed"
    assert _clean_date("0000-00-00") == ""
    assert _clean_date("2026-05-12") == "2026-05-12"


def test_init_db_adds_missing_columns(tmp_path):
    import sqlite3
    from sqlalchemy import create_engine
    from app.database import init_db
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE bills (id INTEGER PRIMARY KEY, state_code VARCHAR(2) NOT NULL, legiscan_bill_id INTEGER NOT NULL, decision VARCHAR(10) NOT NULL)")
    con.commit(); con.close()
    init_db(bind=create_engine(f"sqlite:///{path}"))
    cols = {r[1] for r in sqlite3.connect(path).execute("PRAGMA table_info(bills)")}
    assert "superseded_by" in cols and "bill_title" in cols
