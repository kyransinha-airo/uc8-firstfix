"""Pydantic models shared by the API and services."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    environment: str
    database: str
    llm: str
