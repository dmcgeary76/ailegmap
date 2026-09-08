"""Regression fixture for the title scorer: every bill that has fooled it so far."""
import pytest

from app.sync.legiscan_sync import score_bill, map_status, rank_bills


@pytest.mark.parametrize("title,expected", [
    ("Public schools: artificial intelligence working group.", "HIGH"),
    ("Artificial intelligence: education and workforce development.", "HIGH"),
    ("Leading Ethical AI Development (LEAD) for Kids Act.", "HIGH"),
    ("Relating to the use of artificial intelligence in public school classrooms.", "HIGH"),
    # education in title, AI somewhere in body -> MEDIUM (held for review, not on map)
    ("Student data privacy; requirements for operators.", "MEDIUM"),
    ("Relating to digital citizenship and media literacy instruction in public schools.", "MEDIUM"),
    # title typos / variants still count as an AI term
    ("Requiring the State Board of Education to create model policies on the use of technology and artifical intelligence in schools", "HIGH"),
    ("Artificial-intelligence tools in public school classrooms.", "HIGH"),
    # AI only / neither -> LOW (held for review)
    ("Health care services: artificial intelligence.", "LOW"),
    ("An act relating to state procurement.", "LOW"),
    # higher-ed only -> LOW; higher-ed WITH a K-12 marker stays HIGH
    ("Postsecondary education: artificial intelligence in universities.", "LOW"),
    ("Artificial intelligence in community colleges and K-12 school districts.", "HIGH"),
    # ceremonial / criminal noise -> LOW
    ("Congratulating the Lincoln High School robotics team.", "LOW"),
    ("Crimes: child pornography.", "LOW"),
    ("Budget Act of 2025.", "LOW"),
])
def test_confidence(title, expected):
    assert score_bill({"title": title})["confidence"] == expected


@pytest.mark.xfail(reason="Known gap: title-only scorer promotes a sentencing bill via 'educational materials'. "
                          "Fixed by the description/subjects-based scorer (roadmap step 3).", strict=True)
def test_kansas_hb2537_is_not_high():
    title = ("Increasing the penalties for the crime of sexual extortion when an offender is 18 years of age "
             "or older and the victim is less than 18 years of age or when artificial intelligence is used, "
             "and requiring the attorney general to prepare and provide educational materials and information "
             "concerning such crimes.")
    assert score_bill({"title": title})["confidence"] != "HIGH"


def test_secondary_does_not_match_inside_postsecondary():
    s = score_bill({"title": "Postsecondary education: artificial intelligence."})
    assert "secondary" not in s["title_edu_terms"]


def test_map_status_codes_and_labels():
    assert map_status(4) == ("Passed", "passed")
    assert map_status("5") == ("Vetoed", "failed")
    assert map_status("Signed by Governor")[1] == "passed"
    assert map_status(None) == ("Unknown", None)


def test_rank_prefers_confidence_then_passed_then_relevance():
    ranked = rank_bills([
        {"bill_id": 1, "title": "Artificial intelligence in schools.", "relevance": 10, "status": 1},
        {"bill_id": 2, "title": "Artificial intelligence in schools.", "relevance": 5, "status": 4},
        {"bill_id": 3, "title": "Health care: artificial intelligence.", "relevance": 99, "status": 4},
    ])
    assert [b["bill_id"] for b in ranked] == [2, 1, 3]


def test_only_high_auto_includes():
    from app.models.legislation import Bill
    assert Bill(match_confidence="HIGH", decision="PENDING").effective_included is True
    assert Bill(match_confidence="MEDIUM", decision="PENDING").effective_included is False
    assert Bill(match_confidence="LOW", decision="PENDING").effective_included is False
    assert Bill(match_confidence="MEDIUM", decision="INCLUDED").effective_included is True
    assert Bill(match_confidence="HIGH", decision="EXCLUDED").effective_included is False
    assert score_bill({"title": "Relating to bullying and cyberbullying in public schools."})["is_k12_ai"] is False


def test_short_ai_term_needs_both_boundaries():
    from app.sync.legiscan_sync import score_bill, _matched_terms
    assert _matched_terms("Appropriations: school aid; K-12 school aid", ["ai"]) == []
    assert _matched_terms("Safe and Responsible AI in Schools Act", ["ai"]) == ["ai"]
    assert _matched_terms("(AI) literacy", ["ai"]) == ["ai"]
    s = score_bill({"title": "Appropriations: school aid; appropriations for K-12 school aid; provide for.", "relevance": 20})
    assert s["confidence"] == "LOW" and s["flags"]["noise"]
    s = score_bill({"title": "Enacts into law major components of legislation necessary to implement the state education budget", "relevance": 20})
    assert s["confidence"] == "LOW" and s["flags"]["noise"]
    s = score_bill({"title": "Seckinger High School; inaugural year; innovative artificial intelligence education; honor", "relevance": 20})
    assert s["confidence"] == "LOW" and s["flags"]["noise"]


def test_unchanged_bill_keeps_its_status(db):
    """A bill whose change_hash is unchanged is skipped by getBill; its stored
    status must survive the upsert instead of being overwritten with Unknown."""
    from app.sync.legiscan_sync import LegiScanSync, rank_bills
    from app.models.legislation import Bill
    raw = [{"bill_id": 555, "bill_number": "SB1734", "title": "Schools; artificial intelligence guidance",
            "relevance": 30, "url": "u", "last_action_date": "2026-05-13", "change_hash": "same"}]
    s = LegiScanSync(db=db, api_key="x", fetch_status=False)
    s._upsert_bills("OK", rank_bills(raw))
    b = db.query(Bill).filter_by(legiscan_bill_id=555).one()
    b.bill_status, b.bill_stage = "Passed", "passed"   # as an earlier enriched run stored it
    db.commit()
    s._upsert_bills("OK", rank_bills(raw))             # second sync, hash unchanged, no getBill
    db.refresh(b)
    assert (b.bill_status, b.bill_stage) == ("Passed", "passed")
