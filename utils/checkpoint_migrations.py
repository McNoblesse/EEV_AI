import os
import logging
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection
from config.access_keys import accessKeys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def build_dsn():
    dsn = getattr(accessKeys, "POSTGRES_MEMORY_URL", None)
    if dsn:
        return dsn
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME")
    db_user = os.getenv("DB_USERNAME")
    db_password = os.getenv("DB_PASSWORD")
    if all([db_host, db_name, db_user, db_password]):
        return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    # final fallback
    return getattr(accessKeys, "POSTGRES_URL", None)


def ensure_tables_and_report(dsn: str | None = None):
    """Check for checkpoint-like tables and print counts for quick analytics."""
    if not dsn:
        dsn = build_dsn()
    if not dsn:
        raise RuntimeError("No DSN available for checkpoint migrations. Set POSTGRES_MEMORY_URL or env vars.")

    conn = Connection.connect(dsn)
    try:
        with conn.cursor() as cur:
            # list public tables that look like checkpoints or langgraph artifacts
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND (
                    table_name ILIKE '%checkpoint%'
                    OR table_name ILIKE '%langgraph%'
                    OR table_name ILIKE '%state%'
                    OR table_name ILIKE '%workflow%'
                  )
            """)
            rows = cur.fetchall()
            table_names = [r[0] for r in rows]
            if not table_names:
                logger.warning("No checkpoint-like tables found in public schema.")
            else:
                logger.info("Found checkpoint-like tables: %s", table_names)
                for t in table_names:
                    try:
                        cur.execute(f"SELECT COUNT(*) FROM public.{t}")
                        count = cur.fetchone()[0]
                        logger.info("Table %s has %d rows", t, count)
                    except Exception as e:
                        logger.warning("Could not count rows for table %s: %s", t, e)
            # Example analytics query: show recent 10 entries from first matching table
            if table_names:
                t0 = table_names[0]
                try:
                    cur.execute(f"SELECT * FROM public.{t0} ORDER BY 1 DESC LIMIT 10")
                    recent = cur.fetchall()
                    logger.info("Recent rows from %s: %s", t0, recent)
                except Exception as e:
                    logger.warning("Could not fetch recent rows from %s: %s", t0, e)
    finally:
        conn.close()


def init_postgres_checkpointer(dsn: str | None = None):
    """Create PostgresSaver and run setup() to ensure checkpoint schema exists."""
    if not dsn:
        dsn = build_dsn()
    if not dsn:
        raise RuntimeError("No DSN available for initializing checkpointer.")
    conn = Connection.connect(dsn)
    saver = PostgresSaver(conn)
    try:
        saver.setup()
        logger.info("PostgresSaver setup completed.")
    except Exception as e:
        logger.exception("PostgresSaver.setup() failed: %s", e)
        # Re-raise to ensure caller is aware
        raise
    return saver


if __name__ == "__main__":
    dsn = build_dsn()
    # Initialize checkpointer (creates required tables if missing)
    try:
        init_postgres_checkpointer(dsn)
    except Exception:
        logger.warning("Postgres checkpointer initialization failed; proceeding to table report if possible.")
    ensure_tables_and_report(dsn)
    logger.info("Checkpoint table check complete.")