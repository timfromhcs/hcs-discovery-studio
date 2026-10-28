"""Domain errors with stable machine-readable codes and HTTP mapping."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for expected, user-facing failures."""

    code = "internal_error"
    http_status = 500
    exit_code = 1

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class ValidationError(AppError):
    code = "validation_error"
    http_status = 422
    exit_code = 3


class NotFoundError(AppError):
    code = "not_found"
    http_status = 404
    exit_code = 4


class ConflictError(AppError):
    code = "conflict"
    http_status = 409
    exit_code = 4


class MissingDependencyError(AppError):
    code = "missing_dependency"
    http_status = 424
    exit_code = 5


class PolicyError(AppError):
    code = "policy_blocked"
    http_status = 403
    exit_code = 6


class RunCancelledError(AppError):
    code = "cancelled"
    http_status = 409
    exit_code = 7


class RunFailedError(AppError):
    code = "run_failed"
    http_status = 500
    exit_code = 8
