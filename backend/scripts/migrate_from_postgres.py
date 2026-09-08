"""One-time import from the pre-v0.2 Postgres database into the SQLite file.

Copies:
  * bill_review_queue  -> bills   (including every manual decision/note)
  * state_legislation  -> state_profiles (guidance/stance/context fields only;
                          bill columns and additional_bills are dropped -- the
                          bills table is now the only place bills live)

Run from backend/ with POSTGRES_URL set (see .env.example):

    pip install psycopg2-binary
    python scripts/migrate_from_postgres.py
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from app.database import SessionLocal, init_db, BACKEND_DIR
from app.models.legislation import Bill, StateProfile, JURISDICTIONS

load_dotenv(BACKEND_DIR / ".env")
PG = os.getenv("POSTGRES_URL")
if not PG:
    sys.exit("POSTGRES_URL not set (backend/.env)")

# States whose stance/guidance were researched by hand before v0.2.
RESEARCHED = {"CA", "TX", "MA", "RI", "AK", "HI", "PR", "GU", "VI"}

PROFILE_COLS = [
    "guidance_exists", "guidance_type", "guidance_issued_by", "guidance_issued_date", "guidance_url",
    "guidance_core_principles", "regulatory_stance", "maturity", "key_focus_areas",
    "unique_context", "notes", "sources",
]
BILL_COLS = [
    "state_code", "legiscan_bill_id", "bill_number", "bill_title", "bill_url", "bill_text_url",
    "bill_status", "bill_stage", "status_date", "last_action", "last_action_date",
    "relevance_score", "match_confidence", "flag_reason", "matched_ai_terms", "matched_edu_terms",
    "decision", "decision_note", "reviewed_by", "reviewed_at", "first_seen", "last_seen",
]


def main():
    init_db()
    pg = create_engine(PG)
    db = SessionLocal()
    n_bills = n_prof = 0
    with pg.connect() as conn:
        for row in conn.execute(text("SELECT * FROM bill_review_queue")).mappings():
            if not row["legiscan_bill_id"]:
                continue
            existing = db.query(Bill).filter_by(state_code=row["state_code"],
                                                legiscan_bill_id=row["legiscan_bill_id"]).first()
            bill = existing or Bill()
            for c in BILL_COLS:
                setattr(bill, c, row.get(c))
            if existing is None:
                db.add(bill)
            n_bills += 1

        for row in conn.execute(text("SELECT * FROM state_legislation")).mappings():
            code = row["state_code"]
            if code not in JURISDICTIONS:
                continue
            p = db.query(StateProfile).filter_by(state_code=code).first() or StateProfile(
                state_code=code, state_name=JURISDICTIONS[code])
            for c in PROFILE_COLS:
                if row.get(c) is not None:
                    setattr(p, c, row[c])
            if code in RESEARCHED:
                p.research_status = "RESEARCHED"
            p.last_updated = datetime.utcnow()
            db.add(p)
            n_prof += 1
    db.commit()
    db.close()
    print(f"Imported {n_bills} bills and {n_prof} state profiles into SQLite.")
    print("Next: python -m app.seed  (re-applies data/profiles/*.json on top)")


if __name__ == "__main__":
    main()
