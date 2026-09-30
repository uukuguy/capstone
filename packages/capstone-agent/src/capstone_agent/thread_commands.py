"""Public builders for strict ``capstone-command/1`` envelopes.

Clients use these builders to share command identity, cursor, and payload
validation without importing the Thread store or composing raw JSON by hand.
The builders do not submit commands or maintain a cursor; callers must provide
the verified ``expected_event_seq`` from their projection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .model_identity import validate_model_id


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


def _identifier(value: str, *, name: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name} is invalid")
    return value


def _text(value: str, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is invalid")
    return value


def _cursor(value: int) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("expected_event_seq is invalid")
    return value


@dataclass(frozen=True, slots=True)
class ThreadCommandFactory:
    """Build commands for one Thread/Run identity without submitting them."""

    thread_id: str
    run_id: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.thread_id, name="thread_id")
        if self.run_id is not None:
            _identifier(self.run_id, name="run_id")

    def _command(
        self, kind: str, payload: dict[str, Any], *, expected_event_seq: int,
        command_id: str, idempotency_key: str,
    ) -> dict[str, Any]:
        return {
            "schema": "capstone-command/1",
            "command_id": _identifier(command_id, name="command_id"),
            "idempotency_key": _identifier(idempotency_key, name="idempotency_key"),
            "thread_id": self.thread_id,
            **({"run_id": self.run_id} if self.run_id is not None else {}),
            "kind": _identifier(kind, name="kind"),
            "expected_event_seq": _cursor(expected_event_seq),
            "payload": dict(payload),
        }

    def send_ordinary(self, text: str, **kwargs: Any) -> dict[str, Any]:
        return self._message("send_ordinary", text, **kwargs)

    def send_auto(self, text: str, **kwargs: Any) -> dict[str, Any]:
        return self._message("send_auto", text, **kwargs)

    def send_professional(self, text: str, **kwargs: Any) -> dict[str, Any]:
        return self._message("send_professional", text, **kwargs)

    def send_control(self, text: str, **kwargs: Any) -> dict[str, Any]:
        return self._message("send_control", text, **kwargs)

    def _message(self, kind: str, text: str, **kwargs: Any) -> dict[str, Any]:
        return self._command(kind, {"text": _text(text, name="text")}, **kwargs)

    def switch_model(self, model_id: str, **kwargs: Any) -> dict[str, Any]:
        return self._command(
            "switch_model", {"model_id": validate_model_id(model_id)}, **kwargs,
        )

    def enable_profile(self, profile_id: str, profile_version: str, **kwargs: Any) -> dict[str, Any]:
        return self._command(
            "enable_profile",
            {
                "profile_id": _identifier(profile_id, name="profile_id"),
                "profile_version": _text(profile_version, name="profile_version"),
            },
            **kwargs,
        )

    def disable_profile(self, profile_id: str, profile_version: str, **kwargs: Any) -> dict[str, Any]:
        return self._command(
            "disable_profile",
            {
                "profile_id": _identifier(profile_id, name="profile_id"),
                "profile_version": _text(profile_version, name="profile_version"),
            },
            **kwargs,
        )

    def replace_selection(self, enabled_profiles: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        normalized = []
        for entry in enabled_profiles:
            if set(entry) != {"profile_id", "profile_version"}:
                raise ValueError("enabled_profiles entry is invalid")
            normalized.append({
                "profile_id": _identifier(entry["profile_id"], name="profile_id"),
                "profile_version": _text(entry["profile_version"], name="profile_version"),
            })
        return self._command("replace_selection", {"enabled_profiles": normalized}, **kwargs)

    def cancel_live_attempt(self, attempt_id: str, **kwargs: Any) -> dict[str, Any]:
        return self._command(
            "cancel_live_attempt", {"attempt_id": _identifier(attempt_id, name="attempt_id")}, **kwargs,
        )

    def retry_new_attempt(
        self, *, expected_event_seq: int, command_id: str, idempotency_key: str,
        turn_id: str | None = None, attempt_id: str | None = None,
    ) -> dict[str, Any]:
        if (turn_id is None) == (attempt_id is None):
            raise ValueError("retry target requires exactly one identity")
        if turn_id is not None:
            target_name, target = "turn_id", turn_id
        else:
            assert attempt_id is not None
            target_name, target = "attempt_id", attempt_id
        return self._command(
            "retry_new_attempt", {target_name: _identifier(target, name=target_name)},
            expected_event_seq=expected_event_seq,
            command_id=command_id, idempotency_key=idempotency_key,
        )


__all__ = ["ThreadCommandFactory"]
