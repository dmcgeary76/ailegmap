"""Local (sub-state) actions: derived status, state rollup, seed semantics, API."""
import json
from datetime import date

import pytest

from app import derive
from app.models.legislation import LocalAction
from app.seed import load_local_actions, _validate_action

TODAY = date(2026, 9, 4)


def _a(**kw):
    base = dict(state_code="NY", jurisdiction="X", jurisdiction_type="district", action_type="MORATORIUM",
                direction=-2, lifecycle="adopted", effective_from="2026-09-02", summary="s", sources=[])
    base.update(kw)
    return LocalAction(**base)


def test_status_is_derived_from_dates_and_lifecycle():
    assert derive.action_status(_a(), TODAY) == "active"
    assert derive.action_status(_a(effective_until="2027-06-30"), TODAY) == "active"
    assert derive.action_status(_a(effective_until="2026-06-30"), TODAY) == "expired"
    assert derive.action_status(_a(effective_from="2027-01-01"), TODAY) == "proposed"
    assert derive.action_status(_a(lifecycle="proposed", effective_from=None), TODAY) == "proposed"
    assert derive.action_status(_a(lifecycle="rescinded"), TODAY) == "rescinded"
    # a one-year moratorium stops counting the day after it ends, with no edit
    assert derive.action_status(_a(effective_until="2027-06-30"), date(2027, 7, 1)) == "expired"


def test_local_signal_leaning_and_weighting():
    assert derive.local_signal([], TODAY) == {
        "count": 0, "active": 0, "leaning": None, "score": None, "latest": None, "headline": None}

    nyc = _a(jurisdiction="NYC", enrollment=900000, direction=-2)
    small = _a(jurisdiction="Tiny", enrollment=2000, direction=2, effective_from="2026-08-01")
    sig = derive.local_signal([nyc, small], TODAY)
    assert sig["leaning"] == "restrictive" and sig["score"] < 0     # log-scale size still favors NYC
    assert sig["headline"]["jurisdiction"] == "NYC"
    assert sig["count"] == 2 and sig["active"] == 2 and sig["latest"] == "2026-09-02"

    # expired actions don't move the leaning but still count
    old = _a(jurisdiction="Old", enrollment=900000, direction=-2, effective_from="2024-01-01",
             effective_until="2024-12-31")
    sig = derive.local_signal([old, _a(jurisdiction="Now", direction=1, enrollment=10000)], TODAY)
    assert sig["leaning"] == "permissive" and sig["count"] == 2 and sig["active"] == 1

    # two equal-size opposing actions read as mixed
    sig = derive.local_signal([_a(direction=-1, enrollment=50000), _a(direction=1, enrollment=50000)], TODAY)
    assert sig["leaning"] == "mixed"


def test_sort_actions_active_first_then_size():
    rows = [_a(jurisdiction="expired-big", enrollment=900000, effective_until="2025-01-01", effective_from="2024-01-01"),
            _a(jurisdiction="active-small", enrollment=1000),
            _a(jurisdiction="active-big", enrollment=500000)]
    assert [r.jurisdiction for r in derive.sort_actions(rows, TODAY)] == ["active-big", "active-small", "expired-big"]


def test_seed_validates_and_replaces(db, tmp_path, monkeypatch):
    import app.seed as seed
    monkeypatch.setattr(seed, "LOCAL_ACTION_DIR", tmp_path)
    good = {"jurisdiction": "NYC", "jurisdiction_type": "district", "action_type": "MORATORIUM",
            "direction": -2, "summary": "s", "effective_from": "2026-09-02", "sources": ["u"]}
    (tmp_path / "NY.json").write_text(json.dumps({"state_code": "NY", "actions": [good, dict(good, jurisdiction="Buffalo")]}))
    assert load_local_actions(db) == 2
    assert db.query(LocalAction).count() == 2

    # file is the source of truth: re-seeding with one row leaves one row
    (tmp_path / "NY.json").write_text(json.dumps({"state_code": "NY", "actions": [good]}))
    assert load_local_actions(db) == 1
    assert [a.jurisdiction for a in db.query(LocalAction).all()] == ["NYC"]

    for bad in (dict(good, direction=3), dict(good, action_type="BAN"), dict(good, lifecycle="maybe"),
                dict(good, effective_from="yesterday"), dict(good, bogus=1)):
        with pytest.raises(ValueError):
            _validate_action("NY", 0, bad)


def test_api_exposes_local_signal_and_actions(client, db):
    db.add(_a(jurisdiction="NYC", enrollment=900000, effective_until="2027-06-30", grade_band="PK-8"))
    db.commit()
    ny = client.get("/api/states/NY").json()
    assert ny["local_signal"]["leaning"] == "restrictive"
    assert ny["local_signal"]["headline"]["grade_band"] == "PK-8"
    assert ny["local_actions"][0]["status"] == "active"
    assert ny["research_status"] == "NOT_RESEARCHED"      # gray state, red local marker: both true

    tx = next(s for s in client.get("/api/states").json() if s["state_code"] == "TX")
    assert tx["local_signal"] == {"count": 0, "active": 0, "leaning": None, "score": None, "latest": None, "headline": None}

    rows = client.get("/api/local-actions", params={"status": "active"}).json()
    assert [r["jurisdiction"] for r in rows] == ["NYC"]
    assert client.get("/api/local-actions", params={"state_code": "tx"}).json() == []

    summary = client.get("/api/dashboard/summary").json()
    assert summary["local_actions"] == {"total": 1, "active": 1, "states": 1}
    assert summary["states_by_local_leaning"]["restrictive"] == 1
