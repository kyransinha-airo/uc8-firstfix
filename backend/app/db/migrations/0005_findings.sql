-- What the agents found and what the calculate tools computed. Every claim on screen is a
-- finding with citations; every number on screen comes from a calculation row.

-- One call of a pure calculate tool: inputs, formula, result and the audit record it returned.
CREATE TABLE IF NOT EXISTS calculations (
    calc_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id        BIGINT REFERENCES runs,
    ticket_id     BIGINT REFERENCES tickets,
    tool          TEXT NOT NULL,
    inputs        JSONB NOT NULL,
    formula       TEXT NOT NULL,
    result        JSONB NOT NULL,
    audit         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS calculations_run_idx ON calculations (run_id);

-- A statement an agent submitted: the entitlement, a cause and its evidence, a verification
-- condition. subject names what it is about (a cause id, a condition name).
CREATE TABLE IF NOT EXISTS findings (
    finding_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id           BIGINT NOT NULL REFERENCES runs,
    ticket_id        BIGINT NOT NULL REFERENCES tickets,
    agent            TEXT NOT NULL CHECK (agent IN ('A1', 'A2', 'A3', 'A4')),
    kind             TEXT NOT NULL,
    subject          TEXT,
    evidence_status  TEXT CHECK (evidence_status IN ('found', 'missing', 'conflicting',
                                                     'unverified')),
    statement        TEXT NOT NULL,
    data             JSONB NOT NULL DEFAULT '{}'::jsonb,
    calc_id          BIGINT REFERENCES calculations,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS findings_ticket_idx ON findings (ticket_id, agent);

-- A document citation (page, char offsets into the page text, quoted passage) or a telemetry
-- citation (series and window). Exactly one shape per row.
CREATE TABLE IF NOT EXISTS citations (
    citation_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    finding_id    BIGINT NOT NULL REFERENCES findings,
    source_kind   TEXT NOT NULL CHECK (source_kind IN ('document', 'telemetry')),
    doc_id        TEXT,
    page          INTEGER,
    char_start    INTEGER CHECK (char_start >= 0),
    char_end      INTEGER,
    quote         TEXT,
    series_id     TEXT REFERENCES telemetry_series,
    window_start  TIMESTAMPTZ,
    window_end    TIMESTAMPTZ,
    FOREIGN KEY (doc_id, page) REFERENCES document_pages (doc_id, page),
    CHECK (
        (source_kind = 'document'
            AND doc_id IS NOT NULL AND page IS NOT NULL
            AND char_start IS NOT NULL AND char_end > char_start
            AND coalesce(btrim(quote), '') <> ''
            AND series_id IS NULL AND window_start IS NULL AND window_end IS NULL)
        OR
        (source_kind = 'telemetry'
            AND series_id IS NOT NULL AND window_end > window_start
            AND doc_id IS NULL AND page IS NULL
            AND char_start IS NULL AND char_end IS NULL AND quote IS NULL)
    )
);
CREATE INDEX IF NOT EXISTS citations_finding_idx ON citations (finding_id);
