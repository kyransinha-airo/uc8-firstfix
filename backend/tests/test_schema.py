"""Schema from W-003. Each test gets a throwaway database (see conftest.db_url)."""

import csv
from pathlib import Path

import psycopg
import pytest
from psycopg import errors, sql
from psycopg.types.json import Jsonb

from app.db import MIGRATIONS_DIR, apply_migrations

pytestmark = pytest.mark.integration

ALL_MIGRATIONS = sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql"))
MOCK_DIR = Path(__file__).resolve().parents[2] / "data" / "mock-data"
STRUCTURED = MOCK_DIR / "03_structured"

EXPECTED_TABLES = {
    "audit_events",
    # reference
    "sites", "locations", "assets", "fault_families", "alarm_map", "parts", "supersession",
    "fault_causes", "skill_matrix", "technicians", "certificates", "van_stock", "depot_stock",
    "travel_matrix", "maintenance_intervals", "service_history", "bulletins",
    "agreement_register", "telemetry_series", "telemetry_readings", "parameters",
    # documents
    "documents", "document_pages",
    # intake and runs
    "tickets", "source_reports", "runs", "run_steps", "agent_trajectories",
    # findings
    "calculations", "findings", "citations",
    # dispatch
    "bookings", "exclusions", "options", "option_scores", "decision_records",
    # close-out
    "closeouts", "verdicts", "followups",
}  # fmt: skip

# CSV -> table, in foreign-key order. Every file in 03_structured must be listed.
CSV_TABLES = [
    ("sites", "sites"),
    ("locations", "locations"),
    ("fault_families", "fault_families"),
    ("alarm_map", "alarm_map"),
    ("parts", "parts"),
    ("supersession", "supersession"),
    ("install_base", "assets"),
    ("fault_causes", "fault_causes"),
    ("skill_matrix", "skill_matrix"),
    ("technicians", "technicians"),
    ("certificates", "certificates"),
    ("van_stock", "van_stock"),
    ("depot_stock", "depot_stock"),
    ("travel_matrix", "travel_matrix"),
    ("maintenance_intervals", "maintenance_intervals"),
    ("service_history", "service_history"),
    ("bulletins", "bulletins"),
    ("agreement_register", "agreement_register"),
    ("telemetry_series", "telemetry_series"),
    ("telemetry_readings_pre", "telemetry_readings"),
    ("telemetry_readings_post", "telemetry_readings"),
    ("bookings", "bookings"),
]
RENAMED = {"bookings": {"start": "start_at", "end": "end_at"}}


def _one(conn: psycopg.Connection, query: str, params: tuple = ()):
    return conn.execute(query, params).fetchone()[0]


def _array_columns(conn: psycopg.Connection, table: str) -> set[str]:
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_name = %s AND data_type = 'ARRAY'",
        (table,),
    )
    return {r[0] for r in rows}


def _load_csv(conn: psycopg.Connection, stem: str, table: str) -> int:
    with (STRUCTURED / f"{stem}.csv").open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rename = RENAMED.get(stem, {})
        columns = [rename.get(c, c) for c in reader.fieldnames or []]
        arrays = _array_columns(conn, table)
        rows = []
        for raw in reader:
            row = []
            for col, value in zip(columns, raw.values(), strict=True):
                if col in arrays:
                    row.append([v for v in value.split(";") if v])
                else:
                    row.append(value if value != "" else None)
            rows.append(row)
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.SQL(", ").join(sql.Placeholder() * len(columns)),
    )
    with conn.cursor() as cur:
        cur.executemany(query, rows)
    return len(rows)


@pytest.fixture
def seed(db: psycopg.Connection) -> dict:
    """The minimum reference rows plus one ticket, run and option to hang records on."""
    db.execute(
        "INSERT INTO sites VALUES ('S14', 'Northfield Cold Store', 'Halvorsen Foods',"
        " 'America/Chicago')"
    )
    db.execute("INSERT INTO locations VALUES ('B1', 'base', 'North base')")
    db.execute(
        "INSERT INTO assets VALUES ('CU-2', 'CX450-20817', 'Cryon CX-450', 'cooling_unit',"
        " 'S14', 'Cold storage room', '2022-03-14')"
    )
    db.execute("INSERT INTO fault_families VALUES ('HIGH_SIDE_PRESSURE', 'High side')")
    db.execute(
        "INSERT INTO technicians VALUES ('T1', 'Dana Reyes', 'B1', 3, 'V1', '07:00', '17:00')"
    )
    db.execute(
        "INSERT INTO telemetry_series VALUES ('CU2-FC', 'CU-2', 'fan_current', 'A', 2.8, 3.6, 60)"
    )
    ids: dict = {}
    ids["ticket"] = _one(
        db,
        "INSERT INTO tickets (asset_id, asset_match, site_id, fault_family, clock_start)"
        " VALUES ('CU-2', 'confirmed', 'S14', 'HIGH_SIDE_PRESSURE',"
        " '2026-12-01T09:10:00-06:00') RETURNING ticket_id",
    )
    ids["run"] = _one(
        db,
        "INSERT INTO runs (ticket_id, segment, now_at, llm_mode)"
        " VALUES (%s, 'dispatch', '2026-12-01T09:30:00-06:00', 'replay') RETURNING run_id",
        (ids["ticket"],),
    )
    ids["option"] = _one(
        db,
        "INSERT INTO options (run_id, ticket_id, option_key, tech_id, drive_min, arrival_at,"
        " parts_fit, slack_min) VALUES (%s, %s, 'T1_direct', 'T1', 70,"
        " '2026-12-01T10:40:00-06:00', 'partial', 150) RETURNING option_id",
        (ids["run"], ids["ticket"]),
    )
    db.execute(
        "INSERT INTO bookings (booking_id, tech_id, ticket_id, site_id, start_at, end_at,"
        " source) VALUES ('BK-T1', 'T1', %s, 'S14', '2026-12-01T12:55:00-06:00',"
        " '2026-12-01T14:00:00-06:00', 'dispatcher')",
        (ids["ticket"],),
    )
    ids["booking"] = "BK-T1"
    return ids


def _add_decision(db: psycopg.Connection, seed: dict, **overrides) -> int:
    values = {
        "ticket_id": seed["ticket"],
        "run_id": seed["run"],
        "decided_via": "dispatcher",
        "inputs_snapshot": Jsonb({"due_at": "2026-12-01T13:10:00-06:00"}),
        "options": Jsonb([{"option_key": "T1_D2"}]),
        "scores": Jsonb({"T1_D2": "0.60"}),
        "choice": "T1_D2",
        "booking_id": seed["booking"],
        "reason_codes": ["CAUSES_NOT_SEPARABLE", "NO_FULL_FIT_WITH_MIN_SLACK"],
        "decided_by": "dispatcher",
        "reason": "Full parts fit; 15 min slack accepted",
        "decided_at": "2026-12-01T09:40:00-06:00",
        "locked": True,
        "locked_at": "2026-12-01T09:40:00-06:00",
    }
    values.update(overrides)
    query = sql.SQL("INSERT INTO decision_records ({}) VALUES ({}) RETURNING decision_id").format(
        sql.SQL(", ").join(map(sql.Identifier, values)),
        sql.SQL(", ").join(sql.Placeholder() * len(values)),
    )
    return _one(db, query, tuple(values.values()))


# Migrations


def test_migrations_apply_cleanly_twice(db_url):
    assert apply_migrations(db_url) == ALL_MIGRATIONS
    assert apply_migrations(db_url) == []


def test_migration_sql_is_rerunnable(db, db_url):
    # Even replayed outside the runner's bookkeeping, every file applies without error.
    for name in ALL_MIGRATIONS:
        db.execute((MIGRATIONS_DIR / name).read_text())
    assert apply_migrations(db_url) == []


def test_all_tables_exist(db):
    rows = db.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    assert {r[0] for r in rows} - {"schema_migrations"} == EXPECTED_TABLES


# Reference data fits the schema


def test_every_structured_csv_has_a_table():
    assert {p.stem for p in STRUCTURED.glob("*.csv")} == {stem for stem, _ in CSV_TABLES}


def test_mock_reference_data_loads(db):
    for stem, table in CSV_TABLES:
        _load_csv(db, stem, table)
    assert _one(db, "SELECT likely_parts FROM fault_causes WHERE cause_id = 'C1'") == [
        "FM-220",
        "C-35",
    ]
    assert (
        _one(db, "SELECT assets_mentioned FROM agreement_register WHERE doc_id = 'AGR-0412'") == []
    )
    assert _one(db, "SELECT locked FROM bookings WHERE booking_id = 'BK-5520'") is True
    assert _one(db, "SELECT count(DISTINCT series_id) FROM telemetry_readings") == 2


def test_parameters_load_as_jsonb(db):
    yaml = pytest.importorskip("yaml")
    params = yaml.safe_load((MOCK_DIR / "04_config" / "parameters.yaml").read_text())
    with db.cursor() as cur:
        cur.executemany(
            "INSERT INTO parameters (name, value) VALUES (%s, %s)",
            [(k, Jsonb(v)) for k, v in params.items()],
        )
    get = "SELECT value #>> %s FROM parameters WHERE name = %s"
    assert _one(db, get, ("{}", "auto_book_score")) == "0.75"
    assert _one(db, get, ("{weights,travel}", "scoring")) == "0.25"


# Decision records: immutable once locked (NFR-008)


def test_locked_decision_record_rejects_update(db, seed):
    decision = _add_decision(db, seed)
    with pytest.raises(errors.RestrictViolation, match="decision_records is locked"):
        db.execute(
            "UPDATE decision_records SET reason = 'changed' WHERE decision_id = %s", (decision,)
        )


def test_locked_decision_record_rejects_delete(db, seed):
    decision = _add_decision(db, seed)
    with pytest.raises(errors.RestrictViolation, match="decision_records is locked"):
        db.execute("DELETE FROM decision_records WHERE decision_id = %s", (decision,))


def test_unlocked_decision_record_can_be_locked_then_not_changed(db, seed):
    decision = _add_decision(db, seed, locked=False, locked_at=None)
    db.execute(
        "UPDATE decision_records SET locked = true, locked_at = decided_at WHERE decision_id = %s",
        (decision,),
    )
    with pytest.raises(errors.RestrictViolation):
        db.execute(
            "UPDATE decision_records SET locked = false, locked_at = NULL WHERE decision_id = %s",
            (decision,),
        )


def test_correction_supersedes_once(db, seed):
    first = _add_decision(db, seed)
    _add_decision(db, seed, supersedes=first, reason="Corrected booking")
    with pytest.raises(errors.UniqueViolation):
        _add_decision(db, seed, supersedes=first, reason="Second correction of the same")


def test_truncate_still_resets_decision_records(db, seed):
    _add_decision(db, seed)
    db.execute("TRUNCATE decision_records")
    assert _one(db, "SELECT count(*) FROM decision_records") == 0


@pytest.mark.parametrize("reason", ["", "   "])
def test_decision_needs_reason(db, seed, reason):
    with pytest.raises(errors.CheckViolation):
        _add_decision(db, seed, reason=reason)


def test_decision_lock_needs_lock_time(db, seed):
    with pytest.raises(errors.CheckViolation):
        _add_decision(db, seed, locked=True, locked_at=None)


# Bookings: a locked booking never moves (FR-041)


def test_locked_booking_rejects_update_and_delete(db, seed):
    db.execute("UPDATE bookings SET locked = true WHERE booking_id = %s", (seed["booking"],))
    with pytest.raises(errors.RestrictViolation, match="bookings is locked"):
        db.execute(
            "UPDATE bookings SET start_at = start_at + interval '1 hour' WHERE booking_id = %s",
            (seed["booking"],),
        )
    with pytest.raises(errors.RestrictViolation, match="bookings is locked"):
        db.execute("DELETE FROM bookings WHERE booking_id = %s", (seed["booking"],))


# Enums and value checks


@pytest.mark.parametrize("value", ["confirmed", "unconfirmed", "absent"])
def test_coverage_accepted(db, seed, value):
    db.execute("UPDATE tickets SET coverage = %s WHERE ticket_id = %s", (value, seed["ticket"]))


@pytest.mark.parametrize("value", ["covered", "Confirmed", ""])
def test_bad_coverage_rejected(db, seed, value):
    with pytest.raises(errors.CheckViolation):
        db.execute("UPDATE tickets SET coverage = %s WHERE ticket_id = %s", (value, seed["ticket"]))


def test_confirmed_asset_match_needs_asset(db, seed):
    with pytest.raises(errors.CheckViolation):
        db.execute("INSERT INTO tickets (asset_match) VALUES ('confirmed')")
    db.execute("INSERT INTO tickets (asset_match) VALUES ('unconfirmed')")


@pytest.mark.parametrize(
    ("value", "ok"),
    [("found", True), ("missing", True), ("conflicting", True), ("unverified", True),
     ("partial", False), ("Found", False)],
)  # fmt: skip
def test_evidence_status(db, seed, value, ok):
    insert = (
        "INSERT INTO findings (run_id, ticket_id, agent, kind, subject, evidence_status,"
        " statement) VALUES (%s, %s, 'A2', 'evidence', 'C1', %s, 'Fan current dips')"
    )
    params = (seed["run"], seed["ticket"], value)
    if ok:
        db.execute(insert, params)
    else:
        with pytest.raises(errors.CheckViolation):
            db.execute(insert, params)


@pytest.mark.parametrize("value", ["full", "partial", "none"])
def test_parts_fit_accepted(db, seed, value):
    db.execute("UPDATE options SET parts_fit = %s WHERE option_id = %s", (value, seed["option"]))


def test_bad_parts_fit_rejected(db, seed):
    with pytest.raises(errors.CheckViolation):
        db.execute("UPDATE options SET parts_fit = 'some' WHERE option_id = %s", (seed["option"],))


def test_breach_follows_slack(db, seed):
    assert _one(db, "SELECT breach FROM options WHERE option_id = %s", (seed["option"],)) is False
    db.execute("UPDATE options SET slack_min = -10 WHERE option_id = %s", (seed["option"],))
    assert _one(db, "SELECT breach FROM options WHERE option_id = %s", (seed["option"],)) is True


def test_scores_are_two_decimal_and_in_range(db, seed):
    db.execute(
        "INSERT INTO option_scores (option_id, travel, slack, parts, skill, total)"
        " VALUES (%s, 0.708, 0.625, 0.5, 1, 0.71)",
        (seed["option"],),
    )
    assert str(_one(db, "SELECT travel FROM option_scores")) == "0.71"
    with pytest.raises(errors.CheckViolation):
        db.execute("UPDATE option_scores SET total = 1.2")


def test_pinned_trajectory_needs_approver(db, seed):
    insert = (
        "INSERT INTO agent_trajectories (run_id, agent, step, tool, input_hash, prompt_version,"
        " pinned, approved_by) VALUES (%s, 'A1', %s, 'compute_deadline', 'h', 'a1-v1', true, %s)"
    )
    with pytest.raises(errors.CheckViolation):
        db.execute(insert, (seed["run"], 1, None))
    db.execute(insert, (seed["run"], 1, "kyran"))


def test_citation_shapes(db, seed):
    db.execute(
        "INSERT INTO documents (doc_id, doc_type, title, source_path, sha256, page_count,"
        " extractor_version, pack_version) VALUES ('AGR-0412-AM2', 'amendment', 'Amendment 2',"
        " 'agreements/am2.md', %s, 1, 'md-1', 'p1')",
        ("a" * 64,),
    )
    db.execute(
        "INSERT INTO document_pages VALUES ('AGR-0412-AM2', 1, 'CU-2 moves to Schedule B.',"
        " 0, 25, 'md-1', 'p1')"
    )
    finding = _one(
        db,
        "INSERT INTO findings (run_id, ticket_id, agent, kind, statement)"
        " VALUES (%s, %s, 'A1', 'entitlement', 'Schedule B governs') RETURNING finding_id",
        (seed["run"], seed["ticket"]),
    )
    doc = (
        "INSERT INTO citations (finding_id, source_kind, doc_id, page, char_start, char_end,"
        " quote) VALUES (%s, 'document', 'AGR-0412-AM2', %s, 0, 24, %s)"
    )
    db.execute(doc, (finding, 1, "CU-2 moves to Schedule B"))
    with pytest.raises(errors.ForeignKeyViolation):
        db.execute(doc, (finding, 2, "a page that does not exist"))
    with pytest.raises(errors.CheckViolation):
        db.execute(doc, (finding, 1, " "))

    tele = (
        "INSERT INTO citations (finding_id, source_kind, series_id, window_start, window_end)"
        " VALUES (%s, 'telemetry', 'CU2-FC', %s, %s)"
    )
    db.execute(tele, (finding, "2026-12-01T14:05:00-06:00", "2026-12-01T16:05:00-06:00"))
    with pytest.raises(errors.CheckViolation):
        db.execute(tele, (finding, "2026-12-01T16:05:00-06:00", "2026-12-01T14:05:00-06:00"))


# Close-out, verdict and follow-up (G-2)


@pytest.fixture
def verdict(db, seed) -> int:
    closeout = _one(
        db,
        "INSERT INTO closeouts (ticket_id, booking_id, notes, parts_used, marked_resolved,"
        " submitted_by, submitted_at) VALUES (%s, %s, 'Coil cleaned; fan noisy',"
        " '{COIL-CLN}', true, 'dispatcher', '2026-12-01T14:05:00-06:00') RETURNING closeout_id",
        (seed["ticket"], seed["booking"]),
    )
    return _one(
        db,
        "INSERT INTO verdicts (run_id, ticket_id, closeout_id, verdict)"
        " VALUES (%s, %s, %s, 'not_verified') RETURNING verdict_id",
        (seed["run"], seed["ticket"], closeout),
    )


@pytest.mark.parametrize("value", ["verified", "resolved", "Not_Verified"])
def test_verdict_values(db, verdict, value):
    update = "UPDATE verdicts SET verdict = %s WHERE verdict_id = %s"
    if value == "verified":
        db.execute(update, (value, verdict))
    else:
        with pytest.raises(errors.CheckViolation):
            db.execute(update, (value, verdict))


def test_rejecting_verdict_needs_reason(db, verdict):
    with pytest.raises(errors.CheckViolation):
        db.execute(
            "UPDATE verdicts SET review = 'rejected', reviewed_by = 'dispatcher',"
            " reviewed_at = now() WHERE verdict_id = %s",
            (verdict,),
        )


def _propose(db, seed, verdict) -> int:
    return _one(
        db,
        "INSERT INTO followups (ticket_id, verdict_id, proposal)"
        " VALUES (%s, %s, 'Replace fan motor FM-220') RETURNING followup_id",
        (seed["ticket"], verdict),
    )


def test_followup_starts_proposed(db, seed, verdict):
    with pytest.raises(errors.RestrictViolation, match="starts as proposed"):
        db.execute(
            "INSERT INTO followups (ticket_id, verdict_id, proposal, status, decided_by,"
            " decided_at) VALUES (%s, %s, 'x', 'confirmed', 'dispatcher', now())",
            (seed["ticket"], verdict),
        )


def test_followup_confirmed_once_then_fixed(db, seed, verdict):
    followup = _propose(db, seed, verdict)
    with pytest.raises(errors.CheckViolation):  # confirming needs who and when
        db.execute("UPDATE followups SET status = 'confirmed' WHERE followup_id = %s", (followup,))
    db.execute(
        "UPDATE followups SET status = 'confirmed', decided_by = 'dispatcher',"
        " decided_at = '2026-12-01T16:10:00-06:00' WHERE followup_id = %s",
        (followup,),
    )
    with pytest.raises(errors.RestrictViolation, match="cannot change"):
        db.execute("UPDATE followups SET status = 'rejected' WHERE followup_id = %s", (followup,))


def test_declining_followup_needs_reason(db, seed, verdict):
    followup = _propose(db, seed, verdict)
    with pytest.raises(errors.CheckViolation):
        db.execute(
            "UPDATE followups SET status = 'rejected', decided_by = 'dispatcher',"
            " decided_at = now() WHERE followup_id = %s",
            (followup,),
        )


def test_bad_followup_status_rejected(db, seed, verdict):
    followup = _propose(db, seed, verdict)
    with pytest.raises(errors.CheckViolation):
        db.execute(
            "UPDATE followups SET status = 'created', decided_by = 'd', decided_at = now()"
            " WHERE followup_id = %s",
            (followup,),
        )
