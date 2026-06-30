"""
Migration: Add data sync tracking fields and manual review queue.

Adds fields to track where data came from and when it was last synced.
Creates review queue table for manual approval of data changes.
"""

from sqlalchemy import create_engine, text
import os
from datetime import datetime

def upgrade(database_url: str):
    """Apply migration."""
    engine = create_engine(database_url)

    with engine.begin() as connection:
        # Add new columns to state_legislation table
        print("Adding sync tracking columns to state_legislation table...")

        try:
            connection.execute(text("""
                ALTER TABLE state_legislation
                ADD COLUMN IF NOT EXISTS source_url VARCHAR(500);
            """))
            print("  ✅ source_url added")
        except Exception as e:
            print(f"  ⚠️  source_url: {e}")

        try:
            connection.execute(text("""
                ALTER TABLE state_legislation
                ADD COLUMN IF NOT EXISTS last_sync TIMESTAMP;
            """))
            print("  ✅ last_sync added")
        except Exception as e:
            print(f"  ⚠️  last_sync: {e}")

        try:
            connection.execute(text("""
                ALTER TABLE state_legislation
                ADD COLUMN IF NOT EXISTS data_source VARCHAR(50);
            """))
            print("  ✅ data_source added")
        except Exception as e:
            print(f"  ⚠️  data_source: {e}")

        try:
            connection.execute(text("""
                ALTER TABLE state_legislation
                ADD COLUMN IF NOT EXISTS bill_status_date DATE;
            """))
            print("  ✅ bill_status_date added")
        except Exception as e:
            print(f"  ⚠️  bill_status_date: {e}")

        try:
            connection.execute(text("""
                ALTER TABLE state_legislation
                ADD COLUMN IF NOT EXISTS bill_text_url VARCHAR(500);
            """))
            print("  ✅ bill_text_url added")
        except Exception as e:
            print(f"  ⚠️  bill_text_url: {e}")

        # Create data review queue table
        print("\nCreating data_review_queue table...")
        try:
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS data_review_queue (
                    id SERIAL PRIMARY KEY,
                    state_code VARCHAR(2) NOT NULL,
                    field_name VARCHAR(100) NOT NULL,
                    current_value TEXT,
                    proposed_value TEXT NOT NULL,
                    source VARCHAR(100) NOT NULL,
                    status VARCHAR(20) DEFAULT 'PENDING',
                    reviewed_by VARCHAR(255),
                    review_notes TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    reviewed_at TIMESTAMP,
                    CONSTRAINT fk_state
                        FOREIGN KEY (state_code)
                        REFERENCES state_legislation(state_code)
                );
            """))
            print("  ✅ data_review_queue table created")
        except Exception as e:
            print(f"  ⚠️  data_review_queue: {e}")

        # Create indices for performance
        print("\nCreating indices...")
        try:
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_review_queue_status
                ON data_review_queue(status);
            """))
            print("  ✅ review queue status index")
        except Exception as e:
            print(f"  ⚠️  review queue index: {e}")

        try:
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_review_queue_state
                ON data_review_queue(state_code);
            """))
            print("  ✅ review queue state index")
        except Exception as e:
            print(f"  ⚠️  state index: {e}")

    print("\n✅ Migration complete!")


def downgrade(database_url: str):
    """Rollback migration."""
    engine = create_engine(database_url)

    with engine.begin() as connection:
        print("Rolling back migration...")

        try:
            connection.execute(text("DROP TABLE IF EXISTS data_review_queue CASCADE;"))
            print("  ✅ data_review_queue dropped")
        except Exception as e:
            print(f"  ⚠️  {e}")

        try:
            connection.execute(text("""
                ALTER TABLE state_legislation
                DROP COLUMN IF EXISTS source_url;
            """))
            print("  ✅ source_url removed")
        except Exception as e:
            print(f"  ⚠️  {e}")

        try:
            connection.execute(text("""
                ALTER TABLE state_legislation
                DROP COLUMN IF EXISTS last_sync;
            """))
            print("  ✅ last_sync removed")
        except Exception as e:
            print(f"  ⚠️  {e}")

        try:
            connection.execute(text("""
                ALTER TABLE state_legislation
                DROP COLUMN IF EXISTS data_source;
            """))
            print("  ✅ data_source removed")
        except Exception as e:
            print(f"  ⚠️  {e}")

        try:
            connection.execute(text("""
                ALTER TABLE state_legislation
                DROP COLUMN IF EXISTS bill_status_date;
            """))
            print("  ✅ bill_status_date removed")
        except Exception as e:
            print(f"  ⚠️  {e}")

        try:
            connection.execute(text("""
                ALTER TABLE state_legislation
                DROP COLUMN IF EXISTS bill_text_url;
            """))
            print("  ✅ bill_text_url removed")
        except Exception as e:
            print(f"  ⚠️  {e}")

    print("\n✅ Rollback complete!")


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        print("❌ DATABASE_URL not set")
        exit(1)

    import sys
    action = sys.argv[1] if len(sys.argv) > 1 else "upgrade"

    if action == "upgrade":
        upgrade(db_url)
    elif action == "downgrade":
        downgrade(db_url)
    else:
        print(f"Unknown action: {action}")
