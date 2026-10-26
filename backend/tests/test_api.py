from app.models.legislation import JURISDICTIONS
from app.sync.legiscan_sync import LegiScanSync, rank_bills


def _seed(client, db, raw_ca):
    s = LegiScanSync(db=db, fetch_status=False, api_key="x", sleep=0)
    s._ensure_profile("CA")
    s._upsert_bills("CA", rank_bills(raw_ca))


def test_states_lists_every_jurisdiction(client):
    r = client.get("/api/states")
    assert r.status_code == 200
    codes = {s["state_code"] for s in r.json()}
    assert codes == set(JURISDICTIONS)
    tx = next(s for s in r.json() if s["state_code"] == "TX")
    assert tx["legislation_stage"] is None and tx["headline_bill"] is None
    assert tx["research_status"] == "NOT_RESEARCHED"


def test_state_detail_and_review_decision_flow_to_map(client, db, raw_ca):
    _seed(client, db, raw_ca)
    ca = client.get("/api/states/CA").json()
    assert ca["legislation_stage"] == "passed"
    assert ca["headline_bill"]["bill_number"] == "SB1288"
    assert [b["bill_number"] for b in ca["bills"]] == ["SB1288", "AB1064"]
    assert ca["bill_counts"]["held"] == 2

    sb = next(b for b in ca["bills"] if b["bill_number"] == "SB1288")
    r = client.post(f"/api/bills/review/{sb['id']}/decision", json={"decision": "EXCLUDED", "note": "n"})
    assert r.status_code == 200 and r.json()["effective_included"] is False

    ca = client.get("/api/states/CA").json()
    assert ca["headline_bill"]["bill_number"] == "AB1064"
    assert ca["legislation_stage"] == "failed"
    summary = client.get("/api/dashboard/summary").json()
    assert summary["states_by_legislation_stage"]["failed"] == 1
    assert summary["bills"] == {"total": 4, "included": 1, "pending": 3, "excluded": 1}


def test_review_list_filters_in_sql(client, db, raw_ca):
    _seed(client, db, raw_ca)
    on = client.get("/api/bills/review", params={"included": "true", "limit": 1}).json()
    assert len(on) == 1 and on[0]["effective_included"] is True
    off = client.get("/api/bills/review", params={"included": "false"}).json()
    assert {b["bill_number"] for b in off} == {"AB1979", "SB1381"}
    stats = client.get("/api/bills/review/stats", params={"state_code": "CA"}).json()
    assert stats["effective_on_map"] == 2 and stats["needs_review"] == 4
    assert client.post("/api/bills/review/1/decision", json={"decision": "MAYBE"}).status_code == 400


def test_profile_update(client):
    r = client.put("/api/states/AK", json={
        "research_status": "RESEARCHED", "guidance_exists": True, "guidance_type": "ADVISORY",
        "regulatory_stance": "SUPPORT", "maturity": "IN_PROGRESS",
    })
    assert r.status_code == 200 and r.json()["regulatory_stance"] == "SUPPORT"
    support = client.get("/api/states", params={"stance": "SUPPORT"}).json()
    assert [s["state_code"] for s in support] == ["AK"]
    assert client.get("/api/dashboard/summary").json()["states_by_stance"]["SUPPORT"] == 1


def test_dashboard_recent_changes_only_list_on_map_bills(client, db, raw_ca):
    """A sync logs a status change for every tracked bill; the dashboard card
    must show only the ones that are actually on the map."""
    from datetime import datetime, timedelta
    from app.models.legislation import Bill, BillStatusChange
    _seed(client, db, raw_ca)
    bills = {b.bill_number: b for b in db.query(Bill).all()}
    assert bills["SB1288"].effective_included and not bills["SB1381"].effective_included
    t0 = datetime(2026, 1, 1)
    db.add_all([
        BillStatusChange(bill=bills["SB1381"], old_status="Enrolled", new_status="Passed",
                         new_stage="passed", changed_at=t0 + timedelta(days=2)),   # off-map, newest
        BillStatusChange(bill=bills["SB1288"], old_status="Introduced", new_status="Passed",
                         new_stage="passed", changed_at=t0 + timedelta(days=1)),
        BillStatusChange(bill=bills["AB1979"], old_status="Introduced", new_status="Failed",
                         new_stage="failed", changed_at=t0),                       # off-map
    ])
    db.commit()
    recent = client.get("/api/dashboard/summary").json()["recent_status_changes"]
    assert [(c["state_code"], c["bill_number"]) for c in recent] == [("CA", "SB1288")]

    # Excluding the bill drops its change from the card too.
    client.post(f"/api/bills/review/{bills['SB1288'].id}/decision", json={"decision": "EXCLUDED"})
    assert client.get("/api/dashboard/summary").json()["recent_status_changes"] == []
