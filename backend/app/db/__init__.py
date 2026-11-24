"""PostgreSQL access and migrations.

Migrations are plain SQL files in app/db/migrations, applied in name order and recorded
in schema_migrations. Applying is idempotent.
"""

from pathlib import Path

import psycopg

from app.core.config import settings
from app.core.errors import AppError, ErrorCode

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def connect(url: str | None = None) -> psycopg.Connection:
    url = url or settings.database_url
    if not url:
        raise AppError(ErrorCode.NOT_CONFIGURED, "DATABASE_URL is not set")
    return psycopg.connect(url)


def pending_migrations(applied: set[str]) -> list[Path]:
    return [p for p in sorted(MIGRATIONS_DIR.glob("*.sql")) if p.name not in applied]


def apply_migrations(url: str | None = None) -> list[str]:
    """Apply any migrations not yet recorded. Returns the names applied."""
    with connect(url) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        conn.execute("SELECT pg_advisory_xact_lock(8008)")
        applied = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
        done = []
        for path in pending_migrations(applied):
            conn.execute(path.read_text())
            conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
            done.append(path.name)
        return done
