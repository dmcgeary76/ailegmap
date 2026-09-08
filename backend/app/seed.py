"""Load the hand-curated layers from JSON (idempotent).

    python -m app.seed            # load all profiles + local actions
    python -m app.seed CA HI      # load specific jurisdictions

* data/profiles/<ST>.json       -> state_profiles (fields merged onto the row)
* data/local_actions/<ST>.json  -> local_actions  (file replaces the state's rows)
* data/decisions.csv            -> bills.decision (review calls replayed by LegiScan id)
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from app import decisions
from app.database import SessionLocal, init_db, BACKEND_DIR
from app.models.legislation import (
    StateProfile, LocalAction, JURISDICTIONS,
    ACTION_TYPES, JURISDICTION_TYPES, LIFECYCLES, APPLIES_TO,
)

PROFILE_DIR = BACKEND_DIR / "data" / "profiles"
LOCAL_ACTION_DIR = BACKEND_DIR / "data" / "local_actions"
DECISIONS_PATH = decisions.DECISIONS_PATH
LOCAL_ACTION_FIELDS = {
    "jurisdiction", "jurisdiction_type", "action_type", "direction", "applies_to", "grade_band",
    "authority", "lifecycle", "effective_from", "effective_until", "enrollment", "summary",
    "notes", "sources",
}
EDITABLE = {
    "research_status", "guidance_exists", "guidance_type", "guidance_issued_by",
    "guidance_issued_date", "guidance_url", "guidance_core_principles",
    "regulatory_stance", "maturity", "key_focus_areas", "unique_context", "notes", "sources",
}


def load_profiles(db, codes=None) -> int:
    n = 0
    for path in sorted(PROFILE_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        code = data["state_code"].upper()
        if codes and code not in codes:
            continue
        if code not in JURISDICTIONS:
            print(f"  ⚠️  {path.name}: unknown jurisdiction {code}, skipped")
            continue
        profile = db.query(StateProfile).filter_by(state_code=code).first()
        if profile is None:
            profile = StateProfile(state_code=code, state_name=JURISDICTIONS[code])
            db.add(profile)
        for key, value in data.items():
            if key not in EDITABLE:
                continue
            if key == "guidance_issued_date" and isinstance(value, str):
                value = datetime.fromisoformat(value)
            setattr(profile, key, value)
        profile.last_updated = datetime.utcnow()
        n += 1
        print(f"  ✅ {code} {JURISDICTIONS[code]}")
    db.commit()
    return n


def _validate_action(code: str, i: int, a: dict) -> dict:
    """Fail loudly on a malformed row -- a silent bad row would skew the state's leaning."""
    where = f"{code}.json actions[{i}]"
    for req in ("jurisdiction", "jurisdiction_type", "action_type", "direction", "summary"):
        if req not in a:
            raise ValueError(f"{where}: missing '{req}'")
    if a["jurisdiction_type"] not in JURISDICTION_TYPES:
        raise ValueError(f"{where}: jurisdiction_type must be one of {JURISDICTION_TYPES}")
    if a["action_type"] not in ACTION_TYPES:
        raise ValueError(f"{where}: action_type must be one of {ACTION_TYPES}")
    if not isinstance(a["direction"], int) or not -2 <= a["direction"] <= 2:
        raise ValueError(f"{where}: direction must be an integer in -2..2")
    if a.get("lifecycle", "adopted") not in LIFECYCLES:
        raise ValueError(f"{where}: lifecycle must be one of {LIFECYCLES}")
    if a.get("applies_to", "students") not in APPLIES_TO:
        raise ValueError(f"{where}: applies_to must be one of {APPLIES_TO}")
    for f in ("effective_from", "effective_until"):
        if a.get(f):
            datetime.fromisoformat(a[f])  # raises on a bad date
    unknown = set(a) - LOCAL_ACTION_FIELDS
    if unknown:
        raise ValueError(f"{where}: unknown field(s) {sorted(unknown)}")
    return a


def load_local_actions(db, codes=None) -> int:
    """The JSON file is the source of truth: each state's rows are replaced wholesale."""
    n = 0
    if not LOCAL_ACTION_DIR.exists():
        return 0
    for path in sorted(LOCAL_ACTION_DIR.glob("*.json")):
        if path.name.upper() == "README.JSON":
            continue
        data = json.loads(path.read_text())
        code = data["state_code"].upper()
        if codes and code not in codes:
            continue
        if code not in JURISDICTIONS:
            print(f"  ⚠️  {path.name}: unknown jurisdiction {code}, skipped")
            continue
        actions = [_validate_action(code, i, a) for i, a in enumerate(data.get("actions", []))]
        db.query(LocalAction).filter(LocalAction.state_code == code).delete()
        for a in actions:
            db.add(LocalAction(state_code=code, **a))
        n += len(actions)
        print(f"  ✅ {code} {len(actions)} local action(s)")
    db.commit()
    return n


def main():
    init_db()
    codes = {c.upper() for c in sys.argv[1:]} or None
    db = SessionLocal()
    try:
        n = load_profiles(db, codes)
        print()
        m = load_local_actions(db, codes)
        print()
        d = decisions.apply(db)
    finally:
        db.close()
    print(f"\nLoaded {n} profile(s) from {PROFILE_DIR}")
    print(f"Loaded {m} local action(s) from {LOCAL_ACTION_DIR}")
    print(f"Replayed {DECISIONS_PATH.name}: {d} bill decision(s) changed")


if __name__ == "__main__":
    main()
