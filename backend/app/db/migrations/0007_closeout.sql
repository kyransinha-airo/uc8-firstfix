-- Close-out (screen 4 note upload), A4's verdict and gate G-2, and follow-up jobs.

CREATE TABLE IF NOT EXISTS closeouts (
    closeout_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id        BIGINT NOT NULL REFERENCES tickets,
    booking_id       TEXT REFERENCES bookings,
    -- The notes as a document, so A4 can cite them by page and offset.
    doc_id           TEXT REFERENCES documents,
    notes            TEXT NOT NULL CHECK (btrim(notes) <> ''),
    parts_used       TEXT[] NOT NULL DEFAULT '{}',
    marked_resolved  BOOLEAN NOT NULL,
    submitted_by     TEXT NOT NULL,
    submitted_at     TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS closeouts_ticket_idx ON closeouts (ticket_id);

-- A4's verdict and the dispatcher's answer at G-2. Rejecting the verdict needs a reason.
CREATE TABLE IF NOT EXISTS verdicts (
    verdict_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id              BIGINT NOT NULL REFERENCES runs,
    ticket_id           BIGINT NOT NULL REFERENCES tickets,
    closeout_id         BIGINT NOT NULL REFERENCES closeouts,
    verdict             TEXT NOT NULL
                        CHECK (verdict IN ('verified', 'not_verified', 'insufficient_evidence')),
    -- evaluate_conditions output (BR-015 conditions and the gap rule).
    conditions_calc_id  BIGINT REFERENCES calculations,
    rationale           TEXT,
    review              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (review IN ('pending', 'accepted', 'rejected')),
    reviewed_by         TEXT,
    review_reason       TEXT,
    reviewed_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (review = 'pending' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)),
    CHECK (review <> 'rejected' OR coalesce(btrim(review_reason), '') <> '')
);
CREATE INDEX IF NOT EXISTS verdicts_ticket_idx ON verdicts (ticket_id);

-- A follow-up job. A4 proposes it; only the dispatcher at G-2 confirms or rejects it
-- (FR-051). Inserted as proposed; once decided it cannot change. Declining needs a reason.
CREATE TABLE IF NOT EXISTS followups (
    followup_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id        BIGINT NOT NULL REFERENCES tickets,
    verdict_id       BIGINT NOT NULL UNIQUE REFERENCES verdicts,
    proposal         TEXT NOT NULL CHECK (btrim(proposal) <> ''),
    status           TEXT NOT NULL DEFAULT 'proposed'
                     CHECK (status IN ('proposed', 'confirmed', 'rejected')),
    decided_by       TEXT,
    decision_reason  TEXT,
    decided_at       TIMESTAMPTZ,
    -- The ticket created on confirmation (back to A1 entitlement).
    new_ticket_id    BIGINT REFERENCES tickets,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((status = 'proposed') = (decided_by IS NULL AND decided_at IS NULL)),
    CHECK (status <> 'rejected' OR coalesce(btrim(decision_reason), '') <> ''),
    CHECK (new_ticket_id IS NULL OR status = 'confirmed')
);

CREATE OR REPLACE FUNCTION followups_proposed_first() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NEW.status <> 'proposed' THEN
        RAISE EXCEPTION 'a follow-up starts as proposed (got %)', NEW.status
            USING ERRCODE = 'restrict_violation';
    END IF;
    IF TG_OP IN ('UPDATE', 'DELETE') AND OLD.status <> 'proposed' THEN
        RAISE EXCEPTION 'follow-up % is %, it cannot change (% rejected)',
            OLD.followup_id, OLD.status, TG_OP
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$;
CREATE OR REPLACE TRIGGER followups_proposed_first
    BEFORE INSERT OR UPDATE OR DELETE ON followups
    FOR EACH ROW EXECUTE FUNCTION followups_proposed_first();
