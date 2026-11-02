"""Error types for the SDD context module.

Every failure the module can hit is represented by one of these, so the
command line can answer two questions for the operator:

* **what happened** - a stable machine readable code plus a short message,
* **what to do about it** - a concrete hint, usually the exact command.

The codes are part of the contract: the acceptance script and the operator
both match on them, so they must not change silently.
"""

from __future__ import annotations

from typing import Any


class SddctxError(Exception):
    """Base class for every error the module reports to the operator."""

    code = "SDDCTX_ERROR"

    def __init__(self, message: str, hint: str = "", detail: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.detail = detail

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": False,
            "code": self.code,
            "message": self.message,
        }
        if self.hint:
            payload["hint"] = self.hint
        if self.detail:
            payload["detail"] = self.detail
        return payload

    def render(self) -> str:
        """The operator facing text block."""
        lines = [f"[ERROR] {self.code}", f"  发生了什么：{self.message}"]
        if self.hint:
            lines.append(f"  你该做什么：{self.hint}")
        if self.detail:
            lines.append(f"  细节：{self.detail}")
        return "\n".join(lines)


class ConfigError(SddctxError):
    """Something the module needs is not configured."""

    code = "CONFIG_MISSING"


class TaskNotFoundError(SddctxError):
    """The requested task document does not exist."""

    code = "TASK_NOT_FOUND"


class DependencyUnavailableError(SddctxError):
    """seekdb, PowerContext or the model endpoint cannot be reached."""

    code = "DEPENDENCY_UNAVAILABLE"


class StorageError(SddctxError):
    """A seekdb statement failed."""

    code = "STORAGE_FAILED"


class ModelCallError(SddctxError):
    """The model endpoint refused or failed the request."""

    code = "MODEL_CALL_FAILED"


class PatchApplyError(SddctxError):
    """A generated patch could not be applied to the working tree."""

    code = "PATCH_APPLY_FAILED"


class AcceptanceFailureError(SddctxError):
    """An acceptance command failed."""

    code = "TEST_FAILED"


__all__ = [
    "SddctxError",
    "ConfigError",
    "TaskNotFoundError",
    "DependencyUnavailableError",
    "StorageError",
    "ModelCallError",
    "PatchApplyError",
    "AcceptanceFailureError",
]
