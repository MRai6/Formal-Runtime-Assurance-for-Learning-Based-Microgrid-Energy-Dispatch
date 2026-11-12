"""
Database package for PostgreSQL / TimescaleDB telemetry and formal shield audit logging.
"""

from database.connection import (
    get_db_connection,
    check_connection,
    init_tables
)
from database.audit_logger import (
    log_shield_decision,
    flush_shield_decisions,
    log_shield_decisions_batch,
    reset_db_state
)
from database.ingest_telemetry import ingest_telemetry_data

__all__ = [
    "get_db_connection",
    "check_connection",
    "init_tables",
    "log_shield_decision",
    "flush_shield_decisions",
    "log_shield_decisions_batch",
    "reset_db_state",
    "ingest_telemetry_data",
]

