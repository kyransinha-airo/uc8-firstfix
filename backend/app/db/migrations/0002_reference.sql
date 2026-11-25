-- Reference data the deterministic tools read (data/mock-data/03_structured, 04_config).
-- Column names follow the CSV headers so the loader (W-007) maps them one to one; the only
-- renames are bookings.start/end (in 0006) and install_base.csv -> assets. Natural keys from
-- the mock data are the primary keys. Lists in the CSVs (a;b) are TEXT[]. Y/N are BOOLEAN.
-- Every statement is re-runnable.

CREATE TABLE IF NOT EXISTS sites (
    site_id       TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    customer      TEXT NOT NULL,
    timezone      TEXT NOT NULL
);

-- Everywhere a technician can drive from or to: bases, depots and sites.
CREATE TABLE IF NOT EXISTS locations (
    loc_id        TEXT PRIMARY KEY,
    type          TEXT NOT NULL CHECK (type IN ('base', 'depot', 'site')),
    name          TEXT NOT NULL
);

-- Install base (install_base.csv).
CREATE TABLE IF NOT EXISTS assets (
    asset_id          TEXT PRIMARY KEY,
    serial_no         TEXT NOT NULL UNIQUE,
    model             TEXT NOT NULL,
    asset_type        TEXT NOT NULL,
    site_id           TEXT NOT NULL REFERENCES sites,
    location_at_site  TEXT,
    install_date      DATE
);

CREATE TABLE IF NOT EXISTS fault_families (
    fault_family  TEXT PRIMARY KEY,
    description   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alarm_map (
    alarm_code    TEXT PRIMARY KEY,
    description   TEXT NOT NULL,
    fault_family  TEXT NOT NULL REFERENCES fault_families
);

CREATE TABLE IF NOT EXISTS parts (
    part_no       TEXT PRIMARY KEY,
    description   TEXT NOT NULL,
    consumable    BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS supersession (
    old_part_no     TEXT PRIMARY KEY REFERENCES parts,
    new_part_no     TEXT NOT NULL REFERENCES parts,
    effective_from  DATE NOT NULL,
    CHECK (old_part_no <> new_part_no)
);

-- Manufacturer fault table: causes per model and fault family, with priors (OQ-3).
CREATE TABLE IF NOT EXISTS fault_causes (
    model            TEXT NOT NULL,
    fault_family     TEXT NOT NULL REFERENCES fault_families,
    cause_id         TEXT NOT NULL,
    cause            TEXT NOT NULL,
    prior            NUMERIC(4,2) NOT NULL CHECK (prior BETWEEN 0 AND 1),
    procedure_id     TEXT NOT NULL,
    safety_critical  BOOLEAN NOT NULL,
    likely_parts     TEXT[] NOT NULL DEFAULT '{}',
    PRIMARY KEY (model, fault_family, cause_id)
);

CREATE TABLE IF NOT EXISTS skill_matrix (
    fault_family  TEXT NOT NULL REFERENCES fault_families,
    cause_id      TEXT NOT NULL,
    skill         TEXT NOT NULL,
    min_level     SMALLINT NOT NULL CHECK (min_level BETWEEN 1 AND 5),
    certificate   TEXT,
    basis         TEXT,
    PRIMARY KEY (fault_family, cause_id, skill)
);

CREATE TABLE IF NOT EXISTS technicians (
    tech_id              TEXT PRIMARY KEY,
    name                 TEXT NOT NULL,
    home_base            TEXT NOT NULL REFERENCES locations,
    refrigeration_level  SMALLINT NOT NULL CHECK (refrigeration_level BETWEEN 1 AND 5),
    van_id               TEXT NOT NULL UNIQUE,
    shift_start          TIME NOT NULL,
    shift_end            TIME NOT NULL,
    CHECK (shift_end > shift_start)
);

CREATE TABLE IF NOT EXISTS certificates (
    tech_id       TEXT NOT NULL REFERENCES technicians,
    certificate   TEXT NOT NULL,
    cert_no       TEXT NOT NULL,
    issued_on     DATE NOT NULL,
    expires_on    DATE NOT NULL,
    PRIMARY KEY (tech_id, certificate, cert_no),
    CHECK (expires_on >= issued_on)
);

CREATE TABLE IF NOT EXISTS van_stock (
    van_id        TEXT NOT NULL REFERENCES technicians (van_id),
    part_no       TEXT NOT NULL REFERENCES parts,
    qty           INTEGER NOT NULL CHECK (qty >= 0),
    PRIMARY KEY (van_id, part_no)
);

CREATE TABLE IF NOT EXISTS depot_stock (
    depot_id      TEXT NOT NULL REFERENCES locations,
    part_no       TEXT NOT NULL REFERENCES parts,
    qty           INTEGER NOT NULL CHECK (qty >= 0),
    PRIMARY KEY (depot_id, part_no)
);

-- Drive minutes between two locations (one row per direction listed).
CREATE TABLE IF NOT EXISTS travel_matrix (
    from_loc      TEXT NOT NULL REFERENCES locations,
    to_loc        TEXT NOT NULL REFERENCES locations,
    minutes       INTEGER NOT NULL CHECK (minutes >= 0),
    PRIMARY KEY (from_loc, to_loc),
    CHECK (from_loc <> to_loc)
);

CREATE TABLE IF NOT EXISTS maintenance_intervals (
    model            TEXT NOT NULL,
    task             TEXT NOT NULL,
    interval_months  INTEGER NOT NULL CHECK (interval_months > 0),
    PRIMARY KEY (model, task)
);

-- Past jobs. fault_family is free text here: history also holds PLANNED_MAINTENANCE.
-- notes_doc_id points at a document (02_documents/history), loaded separately.
CREATE TABLE IF NOT EXISTS service_history (
    job_id        TEXT PRIMARY KEY,
    asset_id      TEXT NOT NULL REFERENCES assets,
    opened_at     TIMESTAMPTZ NOT NULL,
    closed_at     TIMESTAMPTZ,
    fault_family  TEXT NOT NULL,
    work_done     TEXT,
    parts_used    TEXT[] NOT NULL DEFAULT '{}',
    technician    TEXT REFERENCES technicians,
    notes_doc_id  TEXT,
    CHECK (closed_at IS NULL OR closed_at >= opened_at)
);
CREATE INDEX IF NOT EXISTS service_history_asset_idx ON service_history (asset_id, opened_at);

CREATE TABLE IF NOT EXISTS bulletins (
    bulletin_id   TEXT PRIMARY KEY,
    model         TEXT NOT NULL,
    part_no       TEXT REFERENCES parts,
    issued_on     DATE NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('open', 'closed')),
    doc_id        TEXT
);

-- Pointer table from an agreement to its documents, with effective dates (BR-003).
CREATE TABLE IF NOT EXISTS agreement_register (
    doc_id            TEXT PRIMARY KEY,
    agreement_id      TEXT NOT NULL,
    doc_type          TEXT NOT NULL CHECK (doc_type IN ('agreement', 'schedule', 'amendment')),
    label             TEXT NOT NULL,
    effective_from    DATE NOT NULL,
    effective_to      DATE,
    assets_mentioned  TEXT[] NOT NULL DEFAULT '{}',
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);
CREATE INDEX IF NOT EXISTS agreement_register_agreement_idx
    ON agreement_register (agreement_id);

CREATE TABLE IF NOT EXISTS telemetry_series (
    series_id     TEXT PRIMARY KEY,
    asset_id      TEXT NOT NULL REFERENCES assets,
    metric        TEXT NOT NULL,
    unit          TEXT NOT NULL,
    band_low      NUMERIC(10,3),
    band_high     NUMERIC(10,3),
    interval_sec  INTEGER NOT NULL CHECK (interval_sec > 0),
    CHECK (band_low IS NULL OR band_high IS NULL OR band_low < band_high)
);

-- Pre- and post-visit readings in one table, keyed by series and timestamp.
CREATE TABLE IF NOT EXISTS telemetry_readings (
    series_id     TEXT NOT NULL REFERENCES telemetry_series,
    ts            TIMESTAMPTZ NOT NULL,
    value         NUMERIC(10,3) NOT NULL,
    PRIMARY KEY (series_id, ts)
);

-- parameters.yaml, one row per top-level key (sla, scoring, likelihood, ...).
CREATE TABLE IF NOT EXISTS parameters (
    name          TEXT PRIMARY KEY,
    value         JSONB NOT NULL,
    loaded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
