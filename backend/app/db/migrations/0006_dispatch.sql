-- Dispatch (A3 and gate G-1): bookings, exclusions, options and scores, decision records.
-- Scores are NUMERIC(4,2) on a 0-1 scale (architecture section 7).

-- Calendar entries. Reference rows (bookings.csv: start/end become start_at/end_at) hold
-- other jobs; FirstFix adds the bookings it makes. A locked booking never moves (FR-041):
-- UPDATE and DELETE are rejected once locked. TRUNCATE (demo reset) still works.
CREATE TABLE IF NOT EXISTS bookings (
    booking_id    TEXT PRIMARY KEY,
    tech_id       TEXT NOT NULL REFERENCES technicians,
    ticket_id     BIGINT REFERENCES tickets,
    job_ref       TEXT,
    site_id       TEXT NOT NULL REFERENCES sites,
    start_at      TIMESTAMPTZ NOT NULL,
    end_at        TIMESTAMPTZ NOT NULL,
    source        TEXT NOT NULL DEFAULT 'reference'
                  CHECK (source IN ('reference', 'auto', 'dispatcher')),
    locked        BOOLEAN NOT NULL DEFAULT false,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (end_at > start_at),
    CHECK (ticket_id IS NOT NULL OR job_ref IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS bookings_tech_idx ON bookings (tech_id, start_at);
CREATE OR REPLACE TRIGGER bookings_locked
    BEFORE UPDATE OR DELETE ON bookings
    FOR EACH ROW EXECUTE FUNCTION forbid_change_when_locked();

-- A technician ruled out for a ticket, with the rule that did it (FR-039).
CREATE TABLE IF NOT EXISTS exclusions (
    exclusion_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id        BIGINT NOT NULL REFERENCES runs,
    ticket_id     BIGINT NOT NULL REFERENCES tickets,
    tech_id       TEXT NOT NULL REFERENCES technicians,
    rule          TEXT NOT NULL,
    reason        TEXT NOT NULL CHECK (btrim(reason) <> ''),
    calc_id       BIGINT REFERENCES calculations,
    UNIQUE (run_id, tech_id, rule)
);

-- One way to do the job: a technician, an optional depot detour, an optional booking to
-- follow. option_key is the stable name shown on screen (T1_direct, T1_D2, T4_after).
CREATE TABLE IF NOT EXISTS options (
    option_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id            BIGINT NOT NULL REFERENCES runs,
    ticket_id         BIGINT NOT NULL REFERENCES tickets,
    option_key        TEXT NOT NULL,
    tech_id           TEXT NOT NULL REFERENCES technicians,
    depot_id          TEXT REFERENCES locations,
    after_booking_id  TEXT REFERENCES bookings,
    route             TEXT[] NOT NULL DEFAULT '{}',
    drive_min         INTEGER NOT NULL CHECK (drive_min >= 0),
    arrival_at        TIMESTAMPTZ NOT NULL,
    parts_fit         TEXT NOT NULL CHECK (parts_fit IN ('full', 'partial', 'none')),
    -- Minutes between arrival and the deadline; negative is a breach.
    slack_min         INTEGER,
    breach            BOOLEAN GENERATED ALWAYS AS (slack_min < 0) STORED,
    calc_id           BIGINT REFERENCES calculations,
    UNIQUE (run_id, option_key)
);

CREATE TABLE IF NOT EXISTS option_scores (
    option_id     BIGINT PRIMARY KEY REFERENCES options,
    travel        NUMERIC(4,2) NOT NULL CHECK (travel BETWEEN 0 AND 1),
    -- NULL when there is no SLA (OQ-19: slack n/a, weights renormalised).
    slack         NUMERIC(4,2) CHECK (slack BETWEEN 0 AND 1),
    parts         NUMERIC(4,2) NOT NULL CHECK (parts BETWEEN 0 AND 1),
    skill         NUMERIC(4,2) NOT NULL CHECK (skill BETWEEN 0 AND 1),
    total         NUMERIC(4,2) NOT NULL CHECK (total BETWEEN 0 AND 1),
    calc_id       BIGINT REFERENCES calculations
);

-- The record of one booking decision, auto (A3 via book_auto) or by the dispatcher at G-1.
-- Immutable once locked (NFR-008): UPDATE and DELETE are rejected; TRUNCATE still works.
-- A correction is a new record that supersedes the old one.
CREATE TABLE IF NOT EXISTS decision_records (
    decision_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id         BIGINT NOT NULL REFERENCES tickets,
    run_id            BIGINT REFERENCES runs,
    decided_via       TEXT NOT NULL CHECK (decided_via IN ('auto', 'dispatcher')),
    inputs_snapshot   JSONB NOT NULL,
    options           JSONB NOT NULL,
    scores            JSONB NOT NULL,
    choice            TEXT NOT NULL,
    chosen_option_id  BIGINT REFERENCES options,
    booking_id        TEXT REFERENCES bookings,
    -- Escalation reason codes from A3 (CAUSES_NOT_SEPARABLE, ...); empty for auto-book.
    reason_codes      TEXT[] NOT NULL DEFAULT '{}',
    decided_by        TEXT NOT NULL CHECK (btrim(decided_by) <> ''),
    -- Every booking needs a reason (FR-038).
    reason            TEXT NOT NULL CHECK (btrim(reason) <> ''),
    -- Booked knowing it misses the deadline (BR-013).
    breach            BOOLEAN NOT NULL DEFAULT false,
    decided_at        TIMESTAMPTZ NOT NULL,
    supersedes        BIGINT UNIQUE REFERENCES decision_records,
    locked            BOOLEAN NOT NULL DEFAULT false,
    locked_at         TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (locked = (locked_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS decision_records_ticket_idx ON decision_records (ticket_id);
CREATE OR REPLACE TRIGGER decision_records_locked
    BEFORE UPDATE OR DELETE ON decision_records
    FOR EACH ROW EXECUTE FUNCTION forbid_change_when_locked();
