import pytest

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.llm import LLMConfigurationError, build_llm
from app.db import connect, pending_migrations


def test_llm_config_reports_missing_settings():
    with pytest.raises(LLMConfigurationError, match="AZURE_OPENAI_ENDPOINT"):
        build_llm(Settings(_env_file=None))


def test_v1_endpoint_needs_no_api_version():
    cfg = Settings(
        _env_file=None,
        azure_openai_endpoint="https://example.openai.azure.com/openai/v1",
        azure_openai_api_key="k",
        azure_openai_deployment="d",
    )
    assert build_llm(cfg) is not None


def test_db_connect_without_url_is_not_configured(monkeypatch):
    monkeypatch.setattr("app.db.settings.database_url", None)
    with pytest.raises(AppError) as e:
        connect()
    assert e.value.code == ErrorCode.NOT_CONFIGURED


def test_migrations_are_ordered_and_skip_applied():
    names = [p.name for p in pending_migrations(set())]
    assert names == sorted(names) and names[0].startswith("0001")
    assert pending_migrations(set(names)) == []
