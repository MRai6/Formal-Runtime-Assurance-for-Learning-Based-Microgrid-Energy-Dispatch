import os
import sys
import atexit
import logging
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import psycopg2
from psycopg2.extras import execute_values

# Ensure project paths
_CURRENT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _CURRENT_DIR.parent
if str(_REPO_ROOT / "shared") not in sys.path:
    sys.path.append(str(_REPO_ROOT / "shared"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))

from database.connection import get_db_connection

logger = logging.getLogger("ShieldAuditLogger")

# In-memory buffer for high-throughput runtime simulation logging
_BUFFER: list[tuple] = []
_BUFFER_THRESHOLD = 500
_DB_REACHABLE = True
_WARNED_OFFLINE = False


def reset_db_state():
    """Reset the database connectivity state flag (useful for testing/reconnecting)."""
    global _DB_REACHABLE, _WARNED_OFFLINE
    _DB_REACHABLE = True
    _WARNED_OFFLINE = False


def _format_action(action: Any) -> str | None:
    """Helper to convert actions (float, int, str, None) to standardized VARCHAR(50)."""
    if action is None:
        return None
    if isinstance(action, (float, int)):
        return f"{action:.2f} kW"
    return str(action)[:50]


def log_shield_decision(
    current_soc: float,
    rl_proposed_action: Any,
    shield_intervention_flag: bool,
    shield_fallback_action: Any,
    executed_action: Any,
    computation_latency_ms: float = 0.0,
    violation_reason: str | None = None,
    timestamp: str | datetime | None = None,
    buffer: bool = True
) -> bool:
    """
    Inserts a shield decision record into 'action_audit_log'.
    Fails gracefully with a warning if the database is unreachable, ensuring
    the runtime simulation never crashes.
    
    Args:
        current_soc: Current battery State-of-Charge (0.0 to 1.0).
        rl_proposed_action: Raw action proposed by RL agent (float or string).
        shield_intervention_flag: True if the formal shield intervened to override the action.
        shield_fallback_action: Safe projection action computed by shield (or None).
        executed_action: Actual dispatch command dispatched to the microgrid.
        computation_latency_ms: Execution latency of shield projection in milliseconds.
        violation_reason: Explanation of constraint violation (or None if safe).
        timestamp: Optional timestamp (defaults to current UTC time).
        buffer: If True, queues the record in an in-memory buffer and flushes in batches
                for optimal runtime simulation performance. If False, commits immediately.
                
    Returns:
        bool: True if logged or buffered successfully, False if DB is unreachable.
    """
    global _DB_REACHABLE, _WARNED_OFFLINE

    if not _DB_REACHABLE:
        return False

    # Standardize timestamp
    if timestamp is None:
        ts = datetime.now(timezone.utc)
    elif isinstance(timestamp, str):
        try:
            ts = datetime.fromisoformat(timestamp)
        except ValueError:
            ts = timestamp  # Let PostgreSQL parse string format directly
    else:
        ts = timestamp

    # Standardize fields to match schema types
    record = (
        ts,
        float(current_soc),
        _format_action(rl_proposed_action),
        bool(shield_intervention_flag),
        _format_action(shield_fallback_action),
        _format_action(executed_action),
        float(computation_latency_ms) if computation_latency_ms is not None else 0.0,
        str(violation_reason)[:255] if violation_reason else None
    )

    if buffer:
        _BUFFER.append(record)
        if len(_BUFFER) >= _BUFFER_THRESHOLD:
            return flush_shield_decisions()
        return True

    # Immediate single insert
    insert_sql = """
    INSERT INTO action_audit_log (
        time,
        current_soc,
        rl_proposed_action,
        shield_intervention_flag,
        shield_fallback_action,
        executed_action,
        computation_latency_ms,
        violation_reason
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
    """
    try:
        with get_db_connection(connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(insert_sql, record)
        return True
    except Exception as exc:
        _DB_REACHABLE = False
        if not _WARNED_OFFLINE:
            warnings.warn(
                f"[WARNING] Database unreachable at active DATABASE_URL. Shield audit logging "
                f"disabled for this session (simulation will proceed without database): {exc}",
                RuntimeWarning,
                stacklevel=2
            )
            _WARNED_OFFLINE = True
        return False


def flush_shield_decisions() -> bool:
    """
    Flushes all buffered shield decisions to the database in a single batch insert.
    Fails gracefully if the database is unreachable.
    """
    global _BUFFER, _DB_REACHABLE, _WARNED_OFFLINE

    if not _BUFFER:
        return True

    if not _DB_REACHABLE:
        _BUFFER.clear()
        return False

    insert_sql = """
    INSERT INTO action_audit_log (
        time,
        current_soc,
        rl_proposed_action,
        shield_intervention_flag,
        shield_fallback_action,
        executed_action,
        computation_latency_ms,
        violation_reason
    ) VALUES %s;
    """

    records_to_insert = list(_BUFFER)
    _BUFFER.clear()

    try:
        with get_db_connection(connect_timeout=3) as conn:
            with conn.cursor() as cur:
                execute_values(cur, insert_sql, records_to_insert, page_size=1000)
        return True
    except Exception as exc:
        _DB_REACHABLE = False
        if not _WARNED_OFFLINE:
            warnings.warn(
                f"[WARNING] Database unreachable during audit flush: {exc}. "
                f"Remaining logs discarded for this session.",
                RuntimeWarning,
                stacklevel=2
            )
            _WARNED_OFFLINE = True
        return False


def log_shield_decisions_batch(records: list[dict | tuple]) -> int:
    """
    Bulk inserts a list of decision records directly into 'action_audit_log'.
    Each record can be a dictionary with keys matching the function arguments
    or a tuple matching the column order.
    
    Returns:
        int: Number of records inserted, or 0 if failed.
    """
    global _DB_REACHABLE, _WARNED_OFFLINE
    if not records or not _DB_REACHABLE:
        return 0

    tuples = []
    for r in records:
        if isinstance(r, dict):
            tuples.append((
                r.get("timestamp") or datetime.now(timezone.utc),
                float(r["current_soc"]),
                _format_action(r["rl_proposed_action"]),
                bool(r["shield_intervention_flag"]),
                _format_action(r.get("shield_fallback_action")),
                _format_action(r["executed_action"]),
                float(r.get("computation_latency_ms", 0.0)),
                str(r.get("violation_reason", ""))[:255] if r.get("violation_reason") else None
            ))
        elif isinstance(r, (tuple, list)):
            tuples.append(tuple(r))

    insert_sql = """
    INSERT INTO action_audit_log (
        time,
        current_soc,
        rl_proposed_action,
        shield_intervention_flag,
        shield_fallback_action,
        executed_action,
        computation_latency_ms,
        violation_reason
    ) VALUES %s;
    """
    try:
        with get_db_connection(connect_timeout=3) as conn:
            with conn.cursor() as cur:
                execute_values(cur, insert_sql, tuples, page_size=1000)
        return len(tuples)
    except Exception as exc:
        _DB_REACHABLE = False
        if not _WARNED_OFFLINE:
            warnings.warn(
                f"[WARNING] Database unreachable during batch audit insert: {exc}.",
                RuntimeWarning,
                stacklevel=2
            )
            _WARNED_OFFLINE = True
        return 0


# Register automatic flush at process exit
atexit.register(flush_shield_decisions)

