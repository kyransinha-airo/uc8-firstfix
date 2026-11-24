"""One error type for expected failures, so the API returns a consistent envelope."""

from enum import StrEnum


class ErrorCode(StrEnum):
    NOT_FOUND = "NOT_FOUND"
    INVALID_INPUT = "INVALID_INPUT"
    CONFLICT = "CONFLICT"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"


_HTTP_STATUS = {
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.INVALID_INPUT: 422,
    ErrorCode.CONFLICT: 409,
    ErrorCode.NOT_CONFIGURED: 503,
    ErrorCode.UPSTREAM_ERROR: 502,
}


class AppError(Exception):
    def __init__(self, code: ErrorCode, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    @property
    def http_status(self) -> int:
        return _HTTP_STATUS[self.code]

    def to_dict(self) -> dict:
        return {"code": self.code.value, "message": self.message, "details": self.details}
