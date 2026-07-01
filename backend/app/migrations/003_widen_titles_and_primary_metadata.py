"""
Migration: Widen bill_title columns and add primary-bill sync metadata.

Two independent fixes bundled together:

1. `bill_title` on both `state_legislation` and `bill_review_queue` was
   VARCHAR(255)/VARCHAR(500). Some real LegiScan titles (long statutory
   descriptions, e.g. Kansas HB2537) exceed that, causing
   `psycopg2.errors.StringDataRightTruncation` on insert. Widened to TEXT
   (unlimited, same as bill_url).

2. `state_legislation` had no way to know the confidence/stage/LegiScan id of
   its own *primary* bill -- only bill_number/title/status/url. That meant a
   state's primary bill, once set, could never be replaced by a stronger
   match found on a later sync (a "sticky primary" bug). Adds
   `bill_legiscan_id`, `match_confidence`, `bill_stage` so `_persist()` can
   compare the incoming candidate against the current primary and promote
   the better one.

Run:
    python -m app.migrations.003_widen_titles_and_primary_metadata upgrade
    python -m app.migrations.003_widen_titles_and_primary_metadata downgrade
"""

from sqlalchemy import create_engine, text
import os


def upgrade(database_url: str):
    engine = create_engine(database_url)
    with engine.begin() as connection:
        print("Widening bill_title columns to TEXT...")
        connection.execute(text(
            "ALTER TABLE state_legislation ALTER COLUMN bill_title TYPE TEXT;"
        ))
        connection.execute(text(
            "ALTER TABLE bill_review_queue ALTER COLUMN bill_title TYPE TEXT;"
        ))
        print("  ✅ bill_title widened on state_legislation and bill_review_queue")

        print("Adding primary-bill sync metadata to state_legislation...")
        connection.execute(text("""
            ALTER TABLE state_legislation
                ADD COLUMN IF NOT EXISTS bill_legiscan_id INTEGER,
                ADD COLUMN IF NOT EXISTS match_confidence VARCHAR(10),
                ADD COLUMN IF NOT EXISTS bill_stage VARCHAR(20);
        """))
        print("  ✅ bill_legiscan_id, match_confidence, bill_stage added")
        print("     (NULL on existing rows -- next sync will treat them as")
        print("      unranked and promote the first stronger match it finds)")

    print("\n✅ Migration complete!")


def downgrade(database_url: str):
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("""
            ALTER TABLE state_legislation
                DROP COLUMN IF EXISTS bill_legiscan_id,
                DROP COLUMN IF EXISTS match_confidence,
                DROP COLUMN IF EXISTS bill_stage;
        """))
        print("  ✅ primary-bill sync metadata dropped")
        # Note: bill_title is intentionally NOT reverted to VARCHAR -- shrinking
        # it back could truncate data written since the upgrade.
    print("\n✅ Rollback complete! (bill_title left as TEXT -- see note above)")


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
        print(f"Unknown action: {action}. Use 'upgrade' or 'downgrade'.")
