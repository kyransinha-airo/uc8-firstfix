-- Append-only audit log: every run step, agent call and human decision.
CREATE TABLE IF NOT EXISTS audit_events (
    event_id      BIGSERIAL PRIMARY KEY,
    run_id        TEXT,
    event_type    TEXT NOT NULL,
    component     TEXT,
    actor         TEXT,
    payload       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_events_run_idx ON audit_events (run_id);
