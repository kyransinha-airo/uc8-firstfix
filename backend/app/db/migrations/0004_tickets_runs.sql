-- Intake (A1): raw reports, the ticket they merge into, and the record of every run.
-- Times are TIMESTAMPTZ; durations are integer minutes (*_min). Every statement is re-runnable.

-- Raises when a guarded row changes. TG_ARGV[0] names what is guarded, for the message.
CREATE OR REPLACE FUNCTION forbid_change_when_locked() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.locked THEN
        RAISE EXCEPTION '% is locked (% rejected)', TG_TABLE_NAME, TG_OP
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$;

-- One row per fault. Merged reports keep their own source_reports rows (BR-002).
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asset_id           TEXT REFERENCES assets,
    asset_match        TEXT NOT NULL CHECK (asset_match IN ('confirmed', 'unconfirmed')),
    site_id            TEXT REFERENCES sites,
    fault_family       TEXT REFERENCES fault_families,
    merged_report_ids  TEXT[] NOT NULL DEFAULT '{}',
    clock_start        TIMESTAMPTZ,
    -- Entitlement (A1): governing document, coverage and SLA from compute_deadline.
    governing_doc_id   TEXT REFERENCES agreement_register,
    coverage           TEXT CHECK (coverage IN ('confirmed', 'unconfirmed', 'absent')),
    sla_min            INTEGER CHECK (sla_min > 0),
    due_at             TIMESTAMPTZ,
    status             TEXT NOT NULL DEFAULT 'open'
                       CHECK (status IN ('open', 'held', 'escalated', 'booked',
                                         'closed_out', 'closed')),
    -- A follow-up job points at the ticket it follows up.
    parent_ticket_id   BIGINT REFERENCES tickets,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (asset_match = 'unconfirmed' OR asset_id IS NOT NULL),
    CHECK (due_at IS NULL OR clock_start IS NOT NULL AND due_at > clock_start)
);

-- Every report as received, kept after merge. Fields follow the intake schema: asset ref or
-- serial, site, symptom text, reporter, received_at, fault family (closed list), cited spans.
CREATE TABLE IF NOT EXISTS source_reports (
    report_id     TEXT PRIMARY KEY,
    channel       TEXT NOT NULL
                  CHECK (channel IN ('telemetry_alarm', 'call_note', 'email', 'portal')),
    received_at   TIMESTAMPTZ NOT NULL,
    source_path   TEXT NOT NULL,
    raw           TEXT NOT NULL,
    asset_ref     TEXT,
    serial_no     TEXT,
    site_id       TEXT REFERENCES sites,
    symptom_text  TEXT,
    reporter      TEXT,
    alarm_code    TEXT REFERENCES alarm_map,
    fault_family  TEXT REFERENCES fault_families,
    cited_spans   JSONB NOT NULL DEFAULT '[]'::jsonb,
    ticket_id     BIGINT REFERENCES tickets
);
CREATE INDEX IF NOT EXISTS source_reports_ticket_idx ON source_reports (ticket_id);

-- One run of a graph segment: dispatch (A1 -> A2 -> A3) or close-out (A4).
CREATE TABLE IF NOT EXISTS runs (
    run_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id      BIGINT REFERENCES tickets,
    segment        TEXT NOT NULL CHECK (segment IN ('dispatch', 'closeout')),
    status         TEXT NOT NULL DEFAULT 'running'
                   CHECK (status IN ('running', 'succeeded', 'failed')),
    -- The run's "now", passed in (tools never read the clock).
    now_at         TIMESTAMPTZ NOT NULL,
    llm_mode       TEXT NOT NULL CHECK (llm_mode IN ('live', 'record', 'replay')),
    -- Assembled from tool calls (NFR-003).
    retrieval_log  JSONB NOT NULL DEFAULT '[]'::jsonb,
    error          TEXT,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at    TIMESTAMPTZ,
    CHECK (status <> 'failed' OR error IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS runs_ticket_idx ON runs (ticket_id);

CREATE TABLE IF NOT EXISTS run_steps (
    run_step_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id         BIGINT NOT NULL REFERENCES runs,
    step_no        INTEGER NOT NULL CHECK (step_no >= 1),
    name           TEXT NOT NULL,
    agent          TEXT CHECK (agent IN ('A1', 'A2', 'A3', 'A4')),
    status         TEXT NOT NULL DEFAULT 'running'
                   CHECK (status IN ('running', 'succeeded', 'failed', 'skipped')),
    inputs         JSONB NOT NULL DEFAULT '{}'::jsonb,
    outputs        JSONB NOT NULL DEFAULT '{}'::jsonb,
    retrieval_log  JSONB NOT NULL DEFAULT '[]'::jsonb,
    error          TEXT,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at    TIMESTAMPTZ,
    UNIQUE (run_id, step_no),
    CHECK (status <> 'failed' OR error IS NOT NULL)
);

-- Every agent step: the tool it called, the arguments and the output. Pinned trajectories
-- replay with the model off, keyed by agent + input_hash + prompt_version.
CREATE TABLE IF NOT EXISTS agent_trajectories (
    trajectory_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id          BIGINT NOT NULL REFERENCES runs,
    agent           TEXT NOT NULL CHECK (agent IN ('A1', 'A2', 'A3', 'A4')),
    step            INTEGER NOT NULL CHECK (step >= 1),
    tool            TEXT NOT NULL,
    args            JSONB NOT NULL DEFAULT '{}'::jsonb,
    output          JSONB,
    output_hash     TEXT,
    input_hash      TEXT NOT NULL,
    prompt_version  TEXT NOT NULL,
    approved_by     TEXT,
    pinned          BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, agent, step),
    -- Only a reviewed trajectory can be pinned.
    CHECK (NOT pinned OR coalesce(btrim(approved_by), '') <> '')
);
CREATE INDEX IF NOT EXISTS agent_trajectories_replay_idx
    ON agent_trajectories (agent, input_hash, prompt_version) WHERE pinned;
