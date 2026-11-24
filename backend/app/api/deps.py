"""Request dependencies."""

from collections.abc import Iterator

import psycopg

from app.db import connect


def get_conn() -> Iterator[psycopg.Connection]:
    """One connection per request; commits on success, rolls back on error."""
    with connect() as conn:
        yield conn
