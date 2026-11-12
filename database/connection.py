import os
import sys
import logging
from contextlib import contextmanager
from pathlib import Path
import psycopg2
from psycopg2 import OperationalError, DatabaseError

# Ensure 'shared' is accessible
_CURRENT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _CURRENT_DIR.parent
if str(_REPO_ROOT / "shared") not in sys.path:
    sys.path.append(str(_REPO_ROOT / "shared"))

from config import DATABASE_URL

logger = logging.getLogger("MicrogridDatabase")


@contextmanager
def get_db_connection(database_url: str | None = None, connect_timeout: int = 5):
    """
    Context manager that yields a psycopg2 database connection.
    Automatically commits on success, rolls back on exception, and closes on exit.
    
    Args:
        database_url: Optional connection string override. Defaults to config.DATABASE_URL.
        connect_timeout: Connection timeout in seconds.
    """
    target_url = database_url or DATABASE_URL
    if not target_url:
        raise ValueError(
            "DATABASE_URL is not configured. Please define it in your .env file or environment."
        )

    conn = None
    try:
        conn = psycopg2.connect(target_url, connect_timeout=connect_timeout)
        yield conn
        conn.commit()
    except Exception as exc:
        if conn:
            conn.rollback()
        raise exc
    finally:
        if conn and not conn.closed:
            conn.close()


def check_connection(database_url: str | None = None, timeout: int = 3) -> bool:
    """
    Safely probe whether the PostgreSQL / TimescaleDB instance is reachable.
    Returns True if alive, False otherwise.
    """
    try:
        with get_db_connection(database_url=database_url, connect_timeout=timeout) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                return cur.fetchone() == (1,)
    except (OperationalError, DatabaseError, ValueError) as err:
        logger.debug(f"Database health check failed: {err}")
        return False


def init_tables(database_url: str | None = None, enable_timescaledb: bool | None = None) -> bool:
    """
    Safely initialize schema tables ('microgrid_telemetry' and 'action_audit_log')
    with IF NOT EXISTS semantics. Conditionally enables TimescaleDB hypertables
    if running in TimescaleDB or Docker.
    
    Args:
        database_url: Optional connection string override.
        enable_timescaledb: If True, forces TimescaleDB hypertable setup.
                            If None, auto-detects TimescaleDB extension.
                            If False, keeps tables as standard PostgreSQL.
    
    Returns:
        bool: True if initialization completed successfully, False otherwise.
    """
    base_ddl = """
    CREATE TABLE IF NOT EXISTS microgrid_telemetry (
        time TIMESTAMPTZ NOT NULL,
        solar_generation_kw DOUBLE PRECISION,
        load_demand_kw DOUBLE PRECISION,
        battery_soc_percent DOUBLE PRECISION,
        grid_tariff DOUBLE PRECISION,
        PRIMARY KEY (time)
    );

    CREATE INDEX IF NOT EXISTS idx_microgrid_telemetry_time 
        ON microgrid_telemetry (time DESC);

    CREATE TABLE IF NOT EXISTS action_audit_log (
        time TIMESTAMPTZ NOT NULL,
        current_soc DOUBLE PRECISION,
        rl_proposed_action VARCHAR(50),
        shield_intervention_flag BOOLEAN,
        shield_fallback_action VARCHAR(50),
        executed_action VARCHAR(50),
        computation_latency_ms DOUBLE PRECISION,
        violation_reason VARCHAR(255)
    );

    CREATE INDEX IF NOT EXISTS idx_action_audit_log_time 
        ON action_audit_log (time DESC);

    CREATE INDEX IF NOT EXISTS idx_action_audit_log_intervention 
        ON action_audit_log (shield_intervention_flag);
    """

    try:
        with get_db_connection(database_url=database_url) as conn:
            with conn.cursor() as cur:
                # 1. Execute standard PostgreSQL DDL
                cur.execute(base_ddl)
                # Ensure primary key exists on microgrid_telemetry if created previously without it
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint c
                            JOIN pg_class t ON c.conrelid = t.oid
                            WHERE t.relname = 'microgrid_telemetry' AND c.contype = 'p'
                        ) THEN
                            ALTER TABLE microgrid_telemetry ADD PRIMARY KEY (time);
                        END IF;
                    END $$;
                """)
                print("[DB] Standard tables 'microgrid_telemetry' and 'action_audit_log' verified/created.")

                # 2. Check for TimescaleDB extension
                is_timescale = False
                if enable_timescaledb is not False:
                    try:
                        # Test if timescaledb extension is installed or can be created
                        cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
                        conn.commit()
                        is_timescale = True
                    except Exception:
                        conn.rollback()
                        is_timescale = False

                if is_timescale:
                    print("[DB] TimescaleDB extension active. Configuring hypertables...")
                    try:
                        cur.execute("SELECT create_hypertable('microgrid_telemetry', 'time', if_not_exists => TRUE);")
                        cur.execute("SELECT create_hypertable('action_audit_log', 'time', if_not_exists => TRUE);")
                        conn.commit()
                        print("[DB] Hypertables initialized successfully.")
                    except Exception as ts_err:
                        conn.rollback()
                        print(f"[DB] Note: Hypertable creation skipped: {ts_err}")
                else:
                    print("[DB] Standard PostgreSQL mode active (Neon Cloud / standard Postgres). Hypertables bypassed.")

        return True
    except (OperationalError, DatabaseError, ValueError) as exc:
        print(f"[WARNING] Unable to connect to database to initialize tables: {exc}")
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(f"Testing database connection with DATABASE_URL={DATABASE_URL} ...")
    if check_connection():
        print("[SUCCESS] Database is reachable.")
        init_tables()
    else:
        print("[NOTICE] Database is currently unreachable. Check your .env configuration or start the database service.")

