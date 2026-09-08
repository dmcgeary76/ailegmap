"""Review decisions as a git-tracked file.

``data/decisions.csv`` holds every human include/exclude call, one row per
bill, keyed by LegiScan's bill_id. The database is a cache: ``python -m
app.seed`` replays the file onto the ``bills`` table, and every decision made
through the review API is written back to the file, so cloning the repo and
re-syncing reproduces the curated map exactly. Edit the file by hand if you
like -- it is the source of truth, not the SQLite row.

Columns: state_code, bill_number, legiscan_bill_id, decision, reviewed_by,
reviewed_at, note. ``decision`` is INCLUDED or EXCLUDED; delete a row (or set
PENDING) to hand the bill back to the automatic rule.
"""
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from app.database import BACKEND_DIR
from app.models.legislation import Bill

DECISIONS_PATH = BACKEND_DIR / "data" / "decisions.csv"
FIELDS = ["state_code", "bill_number", "legiscan_bill_id", "decision", "reviewed_by", "reviewed_at", "note"]
VALID = {"INCLUDED", "EXCLUDED", "PENDING"}


def read(path: Optional[Path] = None) -> Dict[int, dict]:
    """legiscan_bill_id -> row. Missing file = no decisions."""
    path = path or DECISIONS_PATH
    if not path.exists():
        return {}
    out = {}
    with path.open(newline="") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            dec = (row.get("decision") or "").strip().upper()
            if dec not in VALID:
                raise ValueError(f"{path.name} line {i}: decision must be one of {sorted(VALID)}, got {dec!r}")
            try:
                bid = int(row["legiscan_bill_id"])
            except (KeyError, ValueError):
                raise ValueError(f"{path.name} line {i}: legiscan_bill_id must be an integer")
            row["decision"] = dec
            out[bid] = row
    return out


def apply(db, path: Optional[Path] = None) -> int:
    """Replay the file onto the bills table. Returns rows changed.

    Bills in the file that the sync hasn't discovered yet are skipped (they
    apply on a later seed). Bills with a decision in the DB but no row in the
    file are left alone -- run ``dump`` to capture them.
    """
    path = path or DECISIONS_PATH
    rows = read(path)
    if not rows:
        return 0
    changed = 0
    for b in db.query(Bill).filter(Bill.legiscan_bill_id.in_(list(rows))).all():
        r = rows[b.legiscan_bill_id]
        if r.get("state_code") and r["state_code"].upper() != b.state_code:
            continue  # same LegiScan id can't be two states, but be safe
        reviewed_at = _parse_dt(r.get("reviewed_at"))
        new = (r["decision"], r.get("note") or None, r.get("reviewed_by") or None, reviewed_at)
        cur = (b.decision, b.decision_note, b.reviewed_by, b.reviewed_at)
        if new != cur:
            b.decision, b.decision_note, b.reviewed_by, b.reviewed_at = new
            changed += 1
    db.commit()
    return changed


def dump(db, path: Optional[Path] = None) -> int:
    """Write every non-PENDING decision in the DB to the file (sorted, stable diffs)."""
    path = path or DECISIONS_PATH
    bills = (db.query(Bill).filter(Bill.decision != "PENDING")
             .order_by(Bill.state_code, Bill.bill_number).all())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for b in bills:
            w.writerow({
                "state_code": b.state_code,
                "bill_number": b.bill_number or "",
                "legiscan_bill_id": b.legiscan_bill_id,
                "decision": b.decision,
                "reviewed_by": b.reviewed_by or "",
                "reviewed_at": b.reviewed_at.isoformat() if b.reviewed_at else "",
                "note": b.decision_note or "",
            })
    return len(bills)


def _parse_dt(v: Optional[str]) -> Optional[datetime]:
    v = (v or "").strip()
    if not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        return None


if __name__ == "__main__":
    import sys
    from app.database import SessionLocal, init_db
    init_db()
    db = SessionLocal()
    try:
        if sys.argv[1:] == ["dump"]:
            print(f"Wrote {dump(db)} decision(s) to {DECISIONS_PATH}")
        else:
            print(f"Applied decisions.csv: {apply(db)} bill(s) changed")
    finally:
        db.close()
