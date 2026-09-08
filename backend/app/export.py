"""Export everything the public map needs to one JSON file.

    python -m app.export                    # writes ../docs/data.json
    python -m app.export --out /tmp/x.json

The static map (docs/) reads this file, so publishing is: sync -> review ->
export -> commit. No server is needed to view the map.
"""
import argparse
import json
from datetime import datetime

from app import derive
from app.database import SessionLocal, init_db, BACKEND_DIR
from app.models.legislation import StateProfile, Bill, SyncRun, LocalAction, JURISDICTIONS
from app.schemas.legislation import BillBrief

DEFAULT_OUT = BACKEND_DIR.parent / "docs" / "data.json"


def build_export(db) -> dict:
    profiles = {p.state_code: p for p in db.query(StateProfile).all()}
    bills_by_state = {}
    for b in db.query(Bill).all():
        bills_by_state.setdefault(b.state_code, []).append(b)
    actions_by_state = {}
    for a in db.query(LocalAction).all():
        actions_by_state.setdefault(a.state_code, []).append(a)
    last_run = (db.query(SyncRun).filter(SyncRun.finished_at.isnot(None))
                .order_by(SyncRun.finished_at.desc()).first())

    states = []
    for code, name in JURISDICTIONS.items():
        p = profiles.get(code)
        bills = bills_by_state.get(code, [])
        included = derive.included_bills(bills)
        actions = actions_by_state.get(code, [])
        entry = {
            "state_code": code,
            "state_name": name,
            "research_status": p.research_status.value if p else "NOT_RESEARCHED",
            "legislation_stage": derive.legislation_stage(bills),
            "bill_counts": derive.review_counts(bills),
            "bills": [BillBrief.model_validate(b).model_dump() for b in included],
            "local_signal": derive.local_signal(actions),
            "local_actions": [
                {**{c.name: getattr(a, c.name) for c in LocalAction.__table__.columns
                    if c.name not in ("id", "added_at")},
                 "status": derive.action_status(a)}
                for a in derive.sort_actions(actions)
            ],
        }
        if p:
            entry.update({
                "guidance_exists": p.guidance_exists,
                "guidance_type": p.guidance_type.value,
                "guidance_issued_by": p.guidance_issued_by,
                "guidance_issued_date": p.guidance_issued_date.isoformat() if p.guidance_issued_date else None,
                "guidance_url": p.guidance_url,
                "guidance_core_principles": p.guidance_core_principles or [],
                "regulatory_stance": p.regulatory_stance.value,
                "maturity": p.maturity.value,
                "key_focus_areas": p.key_focus_areas or [],
                "unique_context": p.unique_context,
                "notes": p.notes,
                "sources": p.sources or [],
                "last_updated": p.last_updated.isoformat() if p.last_updated else None,
            })
        states.append(entry)

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "last_sync": last_run.finished_at.isoformat() + "Z" if last_run else None,
        "states": states,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()
    init_db()
    db = SessionLocal()
    try:
        data = build_export(db)
    finally:
        db.close()
    with open(args.out, "w") as f:
        json.dump(data, f, indent=1, default=str)
    n_bills = sum(len(s["bills"]) for s in data["states"])
    print(f"Wrote {args.out}: {len(data['states'])} jurisdictions, {n_bills} included bills")


if __name__ == "__main__":
    main()
