import uuid
from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo

from app.core.config import settings
from app.db import apply_migrations
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def db_url() -> Iterator[str]:
    """A fresh, empty database for one test, dropped afterwards.

    Created from TEST_ADMIN_URL (a role allowed to CREATE DATABASE, connected to a
    maintenance database such as postgres), from the environment or backend/.env.
    Skipped when TEST_ADMIN_URL is unset.
    """
    admin_url = settings.test_admin_url
    if not admin_url:
        pytest.skip("TEST_ADMIN_URL not set")
    name = f"firstfix_test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        yield make_conninfo(admin_url, dbname=name)
    finally:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )


@pytest.fixture
def db(db_url: str) -> Iterator[psycopg.Connection]:
    """An autocommit connection to a fresh database with all migrations applied."""
    apply_migrations(db_url)
    with psycopg.connect(db_url, autocommit=True) as conn:
        yield conn
