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
