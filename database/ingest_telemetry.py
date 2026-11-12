import os
import sys
import time
import argparse
import logging
from pathlib import Path
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

# Ensure project paths
_CURRENT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _CURRENT_DIR.parent
if str(_REPO_ROOT / "shared") not in sys.path:
    sys.path.append(str(_REPO_ROOT / "shared"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))

from database.connection import get_db_connection, init_tables, check_connection

logger = logging.getLogger("TelemetryIngest")


def ingest_telemetry_data(
    csv_path: str | Path | None = None,
    batch_size: int = 1000,
    ensure_tables: bool = True
) -> int:
    """
    Reads microgrid dataset from CSV and batch-inserts telemetry into PostgreSQL / TimescaleDB.
    
    Args:
        csv_path: Path to the microgrid_data.csv file.
        batch_size: Number of records per batch for psycopg2.extras.execute_values.
        ensure_tables: Whether to run table initialization prior to ingestion.
        
    Returns:
        int: Number of rows successfully ingested, or 0 if failed / unreachable.
    """
    if csv_path is None:
        csv_path = _REPO_ROOT / "shared" / "microgrid_data.csv"
    else:
        csv_path = Path(csv_path)

    if not csv_path.exists():
        print(f"[ERROR] Microgrid CSV file not found at: {csv_path}")
        return 0

    print(f"[INGEST] Reading baseline telemetry dataset from {csv_path} ...")
    df = pd.read_csv(csv_path)
    # Strip potential BOM or whitespace from column names
    df.columns = df.columns.str.strip().str.replace("\ufeff", "", regex=False)

    required_cols = {"timestamp", "solar_kw", "load_kw", "price_inr_kwh"}
    if not required_cols.issubset(set(df.columns)):
        print(f"[ERROR] CSV is missing expected columns {required_cols}. Found: {list(df.columns)}")
        return 0

    total_rows = len(df)
    print(f"[INGEST] Loaded {total_rows} telemetry records from CSV.")

    # Probe DB connection first
    if not check_connection():
        print("[WARNING] Database is currently unreachable. Telemetry ingestion skipped.")
        return 0

    if ensure_tables:
        init_tables()

    # Prepare tuples for execute_values
    # (time, solar_generation_kw, load_demand_kw, battery_soc_percent, grid_tariff)
    # Baseline battery SoC is initialized to 50.0%
    records = []
    for row in df.itertuples():
        records.append((
            str(row.timestamp),
            float(row.solar_kw),
            float(row.load_kw),
            50.0,
            float(row.price_inr_kwh)
        ))

    insert_sql = """
    INSERT INTO microgrid_telemetry (
        time,
        solar_generation_kw,
        load_demand_kw,
        battery_soc_percent,
        grid_tariff
    ) VALUES %s
    ON CONFLICT (time) DO UPDATE SET
        solar_generation_kw = EXCLUDED.solar_generation_kw,
        load_demand_kw = EXCLUDED.load_demand_kw,
        battery_soc_percent = EXCLUDED.battery_soc_percent,
        grid_tariff = EXCLUDED.grid_tariff;
    """

    t0 = time.perf_counter()
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    insert_sql,
                    records,
                    page_size=batch_size
                )
        elapsed = time.perf_counter() - t0
        print(f"[SUCCESS] Successfully ingested {len(records)} records in {elapsed:.2f} seconds.")
        return len(records)
    except Exception as exc:
        print(f"[WARNING] Database ingestion encountered an error: {exc}")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest microgrid telemetry into PostgreSQL / TimescaleDB")
    parser.add_argument("--csv", type=str, default=None, help="Path to microgrid_data.csv")
    parser.add_argument("--batch-size", type=int, default=1000, help="Batch size for insertion")
    args = parser.parse_args()

    ingest_telemetry_data(csv_path=args.csv, batch_size=args.batch_size)

