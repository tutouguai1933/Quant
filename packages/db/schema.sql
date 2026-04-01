-- Quant MVP schema draft
-- Phase 1 scope only: crypto + Binance + Freqtrade control plane.
-- Keep this file dependency-light; avoid extensions until dependency setup is approved.

CREATE TABLE IF NOT EXISTS accounts (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_key VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    venue VARCHAR(32) NOT NULL DEFAULT 'binance',
    account_type VARCHAR(32) NOT NULL DEFAULT 'spot',
    base_currency VARCHAR(16) NOT NULL DEFAULT 'USDT',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT accounts_venue_chk CHECK (venue IN ('binance')),
    CONSTRAINT accounts_status_chk CHECK (status IN ('active', 'disabled', 'archived'))
);

CREATE TABLE IF NOT EXISTS strategies (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    strategy_key VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    producer_type VARCHAR(32) NOT NULL,
    execution_engine VARCHAR(32) NOT NULL DEFAULT 'freqtrade',
    symbols_scope TEXT NOT NULL DEFAULT '*',
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    risk_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT strategies_producer_type_chk CHECK (producer_type IN ('mock', 'qlib', 'rule-based')),
    CONSTRAINT strategies_execution_engine_chk CHECK (execution_engine IN ('freqtrade')),
    CONSTRAINT strategies_status_chk CHECK (status IN ('draft', 'stopped', 'running', 'paused', 'error'))
);

CREATE TABLE IF NOT EXISTS signals (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    strategy_id BIGINT REFERENCES strategies(id) ON DELETE SET NULL,
    source VARCHAR(32) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    side VARCHAR(16) NOT NULL,
    score NUMERIC(12, 6) NOT NULL,
    confidence NUMERIC(8, 6) NOT NULL,
    target_weight NUMERIC(12, 6) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'received',
    generated_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT signals_source_chk CHECK (source IN ('mock', 'qlib', 'rule-based')),
    CONSTRAINT signals_side_chk CHECK (side IN ('long', 'short', 'flat')),
    CONSTRAINT signals_score_chk CHECK (score >= 0),
    CONSTRAINT signals_confidence_chk CHECK (confidence >= 0 AND confidence <= 1),
    CONSTRAINT signals_target_weight_chk CHECK (target_weight >= -1 AND target_weight <= 1),
    CONSTRAINT signals_status_chk CHECK (status IN ('received', 'accepted', 'rejected', 'dispatched', 'expired', 'synced'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_type VARCHAR(32) NOT NULL,
    source VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'queued',
    target_type VARCHAR(32) NOT NULL,
    target_id BIGINT,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error_message TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT tasks_type_chk CHECK (task_type IN ('train', 'signal_ingest', 'risk_check', 'sync', 'reconcile', 'archive', 'health_check')),
    CONSTRAINT tasks_source_chk CHECK (source IN ('system', 'openclaw', 'user', 'scheduler')),
    CONSTRAINT tasks_target_type_chk CHECK (target_type IN ('system', 'account', 'strategy', 'signal', 'order', 'position', 'balance', 'task')),
    CONSTRAINT tasks_status_chk CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'retrying', 'cancelled'))
);

CREATE TABLE IF NOT EXISTS risk_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    signal_id BIGINT REFERENCES signals(id) ON DELETE SET NULL,
    strategy_id BIGINT REFERENCES strategies(id) ON DELETE SET NULL,
    rule_name VARCHAR(64) NOT NULL,
    level VARCHAR(16) NOT NULL,
    decision VARCHAR(16) NOT NULL,
    reason TEXT NOT NULL,
    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT risk_events_level_chk CHECK (level IN ('low', 'medium', 'high', 'critical')),
    CONSTRAINT risk_events_decision_chk CHECK (decision IN ('allow', 'warn', 'block'))
);

CREATE TABLE IF NOT EXISTS orders (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    strategy_id BIGINT REFERENCES strategies(id) ON DELETE SET NULL,
    source_signal_id BIGINT REFERENCES signals(id) ON DELETE SET NULL,
    venue_order_id VARCHAR(128),
    symbol VARCHAR(32) NOT NULL,
    side VARCHAR(8) NOT NULL,
    order_type VARCHAR(16) NOT NULL,
    status VARCHAR(32) NOT NULL,
    quantity NUMERIC(28, 10) NOT NULL,
    price NUMERIC(28, 10),
    executed_qty NUMERIC(28, 10) NOT NULL DEFAULT 0,
    avg_price NUMERIC(28, 10),
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT orders_side_chk CHECK (side IN ('buy', 'sell')),
    CONSTRAINT orders_type_chk CHECK (order_type IN ('market', 'limit')),
    CONSTRAINT orders_quantity_chk CHECK (quantity > 0),
    CONSTRAINT orders_executed_qty_chk CHECK (executed_qty >= 0 AND executed_qty <= quantity),
    CONSTRAINT orders_status_chk CHECK (status IN ('new', 'open', 'partially_filled', 'filled', 'cancelled', 'rejected', 'expired'))
);

CREATE TABLE IF NOT EXISTS positions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    strategy_id BIGINT REFERENCES strategies(id) ON DELETE SET NULL,
    symbol VARCHAR(32) NOT NULL,
    side VARCHAR(16) NOT NULL,
    quantity NUMERIC(28, 10) NOT NULL,
    entry_price NUMERIC(28, 10),
    mark_price NUMERIC(28, 10),
    unrealized_pnl NUMERIC(28, 10) NOT NULL DEFAULT 0,
    opened_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT positions_side_chk CHECK (side IN ('long', 'short')),
    CONSTRAINT positions_quantity_chk CHECK (quantity >= 0),
    CONSTRAINT positions_unique_account_symbol_side UNIQUE (account_id, symbol, side)
);

CREATE TABLE IF NOT EXISTS balances (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    asset VARCHAR(32) NOT NULL,
    total NUMERIC(28, 10) NOT NULL,
    available NUMERIC(28, 10) NOT NULL,
    locked NUMERIC(28, 10) NOT NULL DEFAULT 0,
    snapshot_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT balances_total_chk CHECK (total >= 0),
    CONSTRAINT balances_available_chk CHECK (available >= 0),
    CONSTRAINT balances_locked_chk CHECK (locked >= 0),
    CONSTRAINT balances_amount_consistency_chk CHECK (total = available + locked),
    CONSTRAINT balances_unique_account_asset UNIQUE (account_id, asset)
);

CREATE INDEX IF NOT EXISTS idx_accounts_venue_status
    ON accounts (venue, status);

CREATE INDEX IF NOT EXISTS idx_strategies_status
    ON strategies (status);

CREATE INDEX IF NOT EXISTS idx_signals_strategy_generated_at
    ON signals (strategy_id, generated_at DESC);

CREATE INDEX IF NOT EXISTS idx_signals_status_generated_at
    ON signals (status, generated_at DESC);

CREATE INDEX IF NOT EXISTS idx_tasks_status_requested_at
    ON tasks (status, requested_at DESC);

CREATE INDEX IF NOT EXISTS idx_risk_events_level_event_time
    ON risk_events (level, event_time DESC);

CREATE INDEX IF NOT EXISTS idx_risk_events_signal_id
    ON risk_events (signal_id);

CREATE INDEX IF NOT EXISTS idx_orders_account_status_updated_at
    ON orders (account_id, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_orders_source_signal_id
    ON orders (source_signal_id);

CREATE INDEX IF NOT EXISTS idx_positions_account_symbol
    ON positions (account_id, symbol);

CREATE INDEX IF NOT EXISTS idx_balances_account_snapshot_time
    ON balances (account_id, snapshot_time DESC);
