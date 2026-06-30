"""
Migration: Add bill-level review queue.

Creates `bill_review_queue` -- one row per bill surfaced by the LegiScan sync,
with its automatic relevance classification and a manual include/exclude
decision. Distinct from the field-level `legislation_updates` audit trail.

Run:
    python -m app.migrations.002_add_bill_review_queue upgrade
    python -m app.migrations.002_add_bill_review_queue downgrade
"""

from sqlalchemy import create_engine, text
import os


def upgrade(database_url: str):
    engine = create_engine(database_url)
    with engine.begin() as connection:
        print("Creating bill_review_queue table...")
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS bill_review_queue (
                id SERIAL PRIMARY KEY,
                state_code VARCHAR(2) NOT NULL,
                legiscan_bill_id INTEGER,
                bill_number VARCHAR(50),
                bill_title VARCHAR(500),
                bill_url TEXT,
                bill_text_url TEXT,
                bill_status VARCHAR(50),
                bill_stage VARCHAR(20),
                status_date VARCHAR(20),
                last_action TEXT,
                last_action_date VARCHAR(20),
                relevance_score INTEGER DEFAULT 0,
                match_confidence VARCHAR(10),
                auto_decision VARCHAR(10),
                flag_reason VARCHAR(20),
                matched_ai_terms JSON,
                matched_edu_terms JSON,
                decision VARCHAR(10) DEFAULT 'PENDING',
                decision_note TEXT,
                reviewed_by VARCHAR(100),
                reviewed_at TIMESTAMP,
                first_seen TIMESTAMP DEFAULT NOW(),
                last_seen TIMESTAMP DEFAULT NOW(),
                CONSTRAINT uq_review_state_bill UNIQUE (state_code, legiscan_bill_id)
            );
        """))
        print("  ✅ bill_review_queue created")

        for name, col in [
            ("idx_billreview_state", "state_code"),
            ("idx_billreview_decision", "decision"),
            ("idx_billreview_confidence", "match_confidence"),
            ("idx_billreview_billid", "legiscan_bill_id"),
        ]:
            connection.execute(text(
                f"CREATE INDEX IF NOT EXISTS {name} ON bill_review_queue({col});"
            ))
            print(f"  ✅ index {name}")

    print("\n✅ Migration complete!")


def downgrade(database_url: str):
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS bill_review_queue CASCADE;"))
        print("  ✅ bill_review_queue dropped")
    print("\n✅ Rollback complete!")


if __name__ == "__main__":
    from dotenv import load_dotenv
    import sys

    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL not set")
        exit(1)

    action = sys.argv[1] if len(sys.argv) > 1 else "upgrade"
    if action == "upgrade":
        upgrade(db_url)
    elif action == "downgrade":
        downgrade(db_url)
    else:
        print(f"Unknown action: {action}")
