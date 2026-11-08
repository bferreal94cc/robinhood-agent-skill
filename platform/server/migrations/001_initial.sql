CREATE TABLE IF NOT EXISTS signals (
    id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL,
    error_code TEXT,
    lease_until TIMESTAMPTZ,
    provider_request_id TEXT
);

CREATE INDEX IF NOT EXISTS signals_claim_idx
    ON signals (status, available_at, created_at);

CREATE TABLE IF NOT EXISTS source_events (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    channel TEXT NOT NULL,
    symbol TEXT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL,
    payload TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS source_events_seen_idx
    ON source_events (first_seen_at DESC);
