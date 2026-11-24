"""python -m app.scripts.migrate: apply pending SQL migrations to DATABASE_URL."""

from app.db import apply_migrations

if __name__ == "__main__":
    applied = apply_migrations()
    print(f"applied {len(applied)} migration(s): {', '.join(applied) or 'none pending'}")
