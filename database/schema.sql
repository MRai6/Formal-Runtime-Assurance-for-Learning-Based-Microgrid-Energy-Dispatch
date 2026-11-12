-- ==============================================================================
-- Formal Runtime Assurance for Learning-Based Microgrid Energy Dispatch
-- Database Schema DDL: PostgreSQL / TimescaleDB
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- Table 1: Baseline & Operational Telemetry
-- Stores time-series physical measurements from the microgrid.
-- ------------------------------------------------------------------------------
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

-- ------------------------------------------------------------------------------
-- Table 2: Formal Shield Action Audit Log
-- Logs every RL proposed action, runtime shield projection, verification latency,
-- and safety intervention details.
-- ------------------------------------------------------------------------------
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

-- ==============================================================================
-- TimescaleDB-Specific Commands (Hypertables & Columnar Compression)
--
-- Compatibility Note:
-- - On TimescaleDB Docker / Pinggy instances: Execute the commands below.
-- - On Standard PostgreSQL (e.g. Neon Cloud): Leave commented or bypass, as standard
--   Postgres utilizes standard B-tree indexing on 'time' defined above.
-- ==============================================================================

-- Step A: Enable TimescaleDB Extension (if installed in database container)
-- CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Step B: Convert tables to Hypertables (partitioned by time)
-- SELECT create_hypertable('microgrid_telemetry', 'time', if_not_exists => TRUE);
-- SELECT create_hypertable('action_audit_log', 'time', if_not_exists => TRUE);

-- Step C: Enable Columnar Compression for Telemetry (e.g., compress chunks older than 7 days)
-- ALTER TABLE microgrid_telemetry SET (
--     timescaledb.compress,
--     timescaledb.compress_orderby = 'time DESC'
-- );
-- SELECT add_compression_policy('microgrid_telemetry', INTERVAL '7 days', if_not_exists => TRUE);

-- Step D: Enable Columnar Compression for Audit Logs (segmented by intervention flag)
-- ALTER TABLE action_audit_log SET (
--     timescaledb.compress,
--     timescaledb.compress_segmentby = 'shield_intervention_flag',
--     timescaledb.compress_orderby = 'time DESC'
-- );
-- SELECT add_compression_policy('action_audit_log', INTERVAL '7 days', if_not_exists => TRUE);

