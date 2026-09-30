"""Application-owned composition helpers for the neutral Thread worker seam."""

from __future__ import annotations

from collections.abc import Callable

from .harness import HarnessPiClient, HarnessRuntime, PiPromptSession
from .thread_service import AttemptClaim


class ApplicationPiRuntimeFactory:
    """Turn an application-selected Pi session factory into a Harness factory.

    The application decides how a claimed model context selects its provider,
    Domain Pack, and Authority resources.  This adapter only enforces the
    runtime boundary consumed by the neutral worker.
    """

    def __init__(
        self,
        session_factory: Callable[[AttemptClaim], PiPromptSession],
        *,
        runtime_mode: str = "capstone",
    ) -> None:
        if not callable(session_factory):
            raise TypeError("session_factory must be callable")
        self._session_factory = session_factory
        self._runtime_mode = runtime_mode

    def __call__(self, claim: AttemptClaim) -> HarnessRuntime:
        return HarnessPiClient(
            self._session_factory(claim), runtime_mode=self._runtime_mode,
        )


__all__ = ["ApplicationPiRuntimeFactory"]
