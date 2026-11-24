"""Lazy, validated LLM client for agent nodes and model calls.

Only agent nodes and model-call services use this. Deterministic services never do.
"""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse

from langchain_core.language_models import BaseChatModel
from langchain_openai import AzureChatOpenAI, ChatOpenAI

from app.core.config import Settings, settings


class LLMConfigurationError(RuntimeError):
    """Raised before a model call when the Azure OpenAI configuration is incomplete."""


def _uses_v1_api(endpoint: str) -> bool:
    return urlparse(endpoint).path.rstrip("/").lower().endswith("/v1")


def build_llm(config: Settings) -> BaseChatModel:
    endpoint = config.azure_openai_endpoint
    required = {
        "AZURE_OPENAI_ENDPOINT": endpoint,
        "AZURE_OPENAI_API_KEY": config.azure_openai_api_key,
        "AZURE_OPENAI_DEPLOYMENT": config.azure_openai_deployment,
    }
    if not endpoint or not _uses_v1_api(endpoint):
        required["AZURE_OPENAI_API_VERSION"] = config.azure_openai_api_version
    missing = [k for k, v in required.items() if v is None or not str(v).strip()]
    if missing:
        raise LLMConfigurationError(f"Missing LLM configuration: {', '.join(missing)}")

    assert endpoint is not None
    common: dict = {
        "api_key": config.azure_openai_api_key,
        "timeout": config.azure_openai_timeout_s,
        "max_retries": config.azure_openai_max_retries,
    }
    if config.azure_openai_temperature is not None:
        common["temperature"] = config.azure_openai_temperature
    if _uses_v1_api(endpoint):
        return ChatOpenAI(
            base_url=f"{endpoint.rstrip('/')}/", model=config.azure_openai_deployment, **common
        )
    return AzureChatOpenAI(
        azure_endpoint=endpoint,
        azure_deployment=config.azure_openai_deployment,
        api_version=config.azure_openai_api_version,
        **common,
    )


@lru_cache(maxsize=1)
def get_llm() -> BaseChatModel:
    """Built on first use, not at import, so the app starts without LLM settings."""
    return build_llm(settings)
