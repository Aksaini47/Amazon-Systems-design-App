-- Mahika Postgres schema — Project Alpha
-- File: 001_init_schema.sql
-- Authority: mahika_pipeline_protocol.md §4.1 Phase 1 Foundation deliverables
-- Target: PostgreSQL 16 on Oracle Cloud Always Free VM
-- Voice: court-grade audit trail. Every row is timestamped + immutable
--        once written. State transitions go via new rows in audit_log,
--        never in-place edits.

BEGIN;

-- ─── Extensions ──────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- gen_random_uuid alternative
CREATE EXTENSION IF NOT EXISTS pgcrypto;      -- for gen_random_uuid()

-- ─── Enums ──────────────────────────────────────────────────────────────
DO $$ BEGIN
    CREATE TYPE capture_mode AS ENUM ('PK', 'RT');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE qc_verdict AS ENUM ('ok', 'damaged', 'different', 'damaged_different');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE order_state AS ENUM (
        'captured',          -- evidence bundle exists on NVMe
        'pending_refund',    -- waiting for Amazon refund event
        'claim_queued',      -- refund confirmed, queued for filing
        'claim_filed',       -- SAFE-T claim submitted
        'claim_under_review',
        'claim_info_requested',
        'claim_approved',
        'claim_rejected',
        'claim_appealed',
        'claim_closed',      -- terminal: amount credited to seller balance
        'claim_ineligible'   -- terminal: verdict=ok, no claim path
    );
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE alert_priority AS ENUM ('info', 'low', 'medium', 'high', 'critical');
EXCEPTION WHEN duplicate_object THEN null; END $$;

-- ─── Core: orders ───────────────────────────────────────────────────────
-- One row per Amazon order. Created when an evidence bundle is detected
-- on the active runner's NVMe. Updated as state evolves through the
-- pipeline. Cross-references AWB to allow reverse-lookup.
CREATE TABLE IF NOT EXISTS orders (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id        VARCHAR(32)     NOT NULL UNIQUE,    -- Amazon format: 407-1234567-1234567
    awb             VARCHAR(64),                         -- carrier AWB (when known)
    carrier         VARCHAR(64),                         -- ATS / Delhivery / etc.

    -- Capture metadata (mirrored from mobile meta.json)
    mode            capture_mode    NOT NULL,
    captured_at     TIMESTAMPTZ     NOT NULL,
    storage_path    TEXT            NOT NULL,            -- {STORAGE_ROOT}/orders/{order_id}/

    -- QC + claim state
    verdict         qc_verdict,                          -- null until RT verdict set
    state           order_state     NOT NULL DEFAULT 'captured',

    -- Refund tracking (populated by Phase 4 refund watcher)
    refund_processed_at TIMESTAMPTZ,
    refund_amount_paise BIGINT,                          -- store as paise to avoid float drift

    -- Claim outcome
    claim_id            VARCHAR(64),                     -- Amazon's claim ID once filed
    claim_filed_at      TIMESTAMPTZ,
    claim_closed_at     TIMESTAMPTZ,
    claim_amount_paise  BIGINT,

    -- Bookkeeping
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_orders_state ON orders(state);
CREATE INDEX IF NOT EXISTS idx_orders_awb ON orders(awb) WHERE awb IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_captured_at ON orders(captured_at);
CREATE INDEX IF NOT EXISTS idx_orders_pending_refund ON orders(state, captured_at)
    WHERE state IN ('captured', 'pending_refund');

-- ─── Returns intelligence ────────────────────────────────────────────────
-- Scraped from Amazon Returns page every 8hrs by Phase 4 scraper.
-- One row per return-initiation event from Amazon's perspective.
CREATE TABLE IF NOT EXISTS returns (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id            VARCHAR(32)  NOT NULL,
    return_reason       TEXT,
    return_initiated_at TIMESTAMPTZ,
    expected_delivery   DATE,                            -- when return arrives at warehouse
    return_carrier      VARCHAR(64),
    return_awb          VARCHAR(64),
    scraped_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    FOREIGN KEY (order_id) REFERENCES orders(order_id) DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX IF NOT EXISTS idx_returns_order_id ON returns(order_id);
CREATE INDEX IF NOT EXISTS idx_returns_expected ON returns(expected_delivery)
    WHERE expected_delivery IS NOT NULL;

-- ─── Claims queue ───────────────────────────────────────────────────────
-- Queue of orders eligible for SAFE-T claim filing. Phase 5 (Playwright)
-- pops from this queue. Separate from `orders` table so we can replay
-- the queue without touching order history.
CREATE TABLE IF NOT EXISTS claims (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id            VARCHAR(32)  NOT NULL,
    composite_path      TEXT,                            -- generated by Phase 3
    template_version    VARCHAR(16)  NOT NULL DEFAULT 'v1',
    queued_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),

    -- Filing attempt tracking (matches mobile sync_queue retry semantics)
    attempt_count       SMALLINT     NOT NULL DEFAULT 0,
    last_attempt_at     TIMESTAMPTZ,
    last_error          TEXT,

    -- Outcome (mirrored into orders.* on settlement)
    filed_at            TIMESTAMPTZ,
    amazon_claim_id     VARCHAR(64),
    submission_screenshot TEXT,                          -- {OrderID}_claim_submitted.png

    FOREIGN KEY (order_id) REFERENCES orders(order_id) DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX IF NOT EXISTS idx_claims_queued ON claims(queued_at)
    WHERE filed_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_claims_order_id ON claims(order_id);

-- ─── Evidence index ─────────────────────────────────────────────────────
-- Tracks every file on the NVMe per order. Lets Mahika verify file
-- presence + hash before filing a claim (per mahika.md §7.2 audit rules).
CREATE TABLE IF NOT EXISTS evidence (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id        VARCHAR(32)     NOT NULL,
    asset_type      VARCHAR(32)     NOT NULL,            -- 'PK_video', 'RT_video', 'PK_front', 'compare', 'meta', ...
    file_path       TEXT            NOT NULL,
    file_size_bytes BIGINT          NOT NULL,
    sha256          CHAR(64)        NOT NULL,            -- file content hash (tamper detection)
    captured_at     TIMESTAMPTZ,                          -- when the camera/agent created the file
    indexed_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    FOREIGN KEY (order_id) REFERENCES orders(order_id) DEFERRABLE INITIALLY DEFERRED,
    UNIQUE (order_id, asset_type)                         -- one canonical asset per type per order
);

CREATE INDEX IF NOT EXISTS idx_evidence_order_id ON evidence(order_id);

-- ─── Audit log (court-grade) ────────────────────────────────────────────
-- Every state transition + every action Mahika takes. Append-only.
-- This is the legal record. Never delete rows from this table.
CREATE TABLE IF NOT EXISTS audit_log (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    event_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
    actor               VARCHAR(64)  NOT NULL,            -- 'mahika.refund_watcher', 'mahika.playwright', 'sir.manual', etc.
    runner_id           VARCHAR(64),                       -- which machine took the action (mahika_capture_specs §1.3)
    mahika_version      VARCHAR(32),                       -- traceability
    event_type          VARCHAR(64)  NOT NULL,            -- 'order.captured', 'claim.filed', 'claim.approved', ...
    order_id            VARCHAR(32),                       -- nullable: some events (heartbeat) aren't order-scoped
    state_before        order_state,
    state_after         order_state,
    reason              TEXT,
    screenshot_path     TEXT,                              -- evidence anchor for actions involving Seller Central
    human_intervention  BOOLEAN      NOT NULL DEFAULT false,
    payload             JSONB                              -- arbitrary action-specific data
);

CREATE INDEX IF NOT EXISTS idx_audit_log_event_at ON audit_log(event_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_order_id ON audit_log(order_id) WHERE order_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_audit_log_event_type ON audit_log(event_type);

-- ─── Insights Engine output ─────────────────────────────────────────────
-- Pattern recognition results (mahika.md §4.9). Generated weekly.
CREATE TABLE IF NOT EXISTS insights (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    generated_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    period_start        DATE         NOT NULL,
    period_end          DATE         NOT NULL,
    pattern_type        VARCHAR(64)  NOT NULL,            -- 'approval_rate_by_template', 'rejection_cause', ...
    metric_label        TEXT         NOT NULL,
    metric_value        NUMERIC,
    sample_size         INTEGER,
    payload             JSONB
);

CREATE INDEX IF NOT EXISTS idx_insights_period ON insights(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_insights_type ON insights(pattern_type);

-- ─── Suggestions awaiting Sir's approval ────────────────────────────────
-- Insights Engine output's actionable suggestions. Sir reviews + approves
-- via cockpit. APPROVED suggestions get coded in next iteration. Mahika
-- NEVER auto-implements (per skill §4.9 critical boundary).
CREATE TABLE IF NOT EXISTS suggestions (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    suggested_at    TIMESTAMPTZ     NOT NULL DEFAULT now(),
    insight_id      UUID            REFERENCES insights(id),
    title           VARCHAR(255)    NOT NULL,
    body            TEXT            NOT NULL,
    rationale       TEXT,
    status          VARCHAR(32)     NOT NULL DEFAULT 'pending',  -- pending / approved / rejected / implemented
    decided_at      TIMESTAMPTZ,
    decided_by      VARCHAR(64),                                  -- 'sir.cockpit' typically
    rejection_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_suggestions_status ON suggestions(status);

-- ─── Runner heartbeat ───────────────────────────────────────────────────
-- Single-active-runner enforcement (mahika_capture_specs §1.3 §6.2).
-- The machine with the NVMe + Oracle access updates its heartbeat every
-- 60s. Other machines see active heartbeat + stay idle. Prevents two
-- machines double-filing claims.
CREATE TABLE IF NOT EXISTS runner_heartbeat (
    runner_id           VARCHAR(64)  PRIMARY KEY,         -- machine hostname or UUID
    last_seen_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    nvme_serial         VARCHAR(64),                       -- which NVMe is plugged in
    mahika_version      VARCHAR(32),
    is_active           BOOLEAN      NOT NULL DEFAULT true,
    notes               TEXT
);

CREATE INDEX IF NOT EXISTS idx_heartbeat_active ON runner_heartbeat(is_active, last_seen_at);

-- ─── Refund events (raw SP-API webhook + poll output) ───────────────────
-- Phase 4 refund watcher dumps every SP-API Financial Event here for
-- audit + replay. Order linkage is computed downstream — keeps the raw
-- ingest stupid + fast.
CREATE TABLE IF NOT EXISTS refund_events (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    received_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
    event_source        VARCHAR(32)  NOT NULL,            -- 'sp_api_poll' or 'sp_api_webhook'
    amazon_order_id     VARCHAR(32),
    refund_processed_at TIMESTAMPTZ,
    amount_paise        BIGINT,
    currency            CHAR(3)      NOT NULL DEFAULT 'INR',
    raw_payload         JSONB        NOT NULL,
    processed           BOOLEAN      NOT NULL DEFAULT false  -- has Mahika linked + acted on this?
);

CREATE INDEX IF NOT EXISTS idx_refund_events_unprocessed ON refund_events(processed, received_at)
    WHERE processed = false;
CREATE INDEX IF NOT EXISTS idx_refund_events_order_id ON refund_events(amazon_order_id);

-- ─── Triggers: keep orders.updated_at fresh ─────────────────────────────
CREATE OR REPLACE FUNCTION trg_orders_set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS orders_updated_at ON orders;
CREATE TRIGGER orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION trg_orders_set_updated_at();

-- ─── Initial seed: schema version ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS schema_versions (
    version         VARCHAR(16)     PRIMARY KEY,
    applied_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    description     TEXT
);

INSERT INTO schema_versions (version, description)
VALUES ('001', 'Phase 1 init — orders + returns + claims + evidence + audit_log + insights + suggestions + runner_heartbeat + refund_events')
ON CONFLICT (version) DO NOTHING;

COMMIT;
