"""Application-owned composition helpers for the neutral Thread worker seam."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .harness import HarnessPiClient, HarnessRuntime, PiPromptSession
from .thread_catalog import AuthorityThreadModelCatalog
from .thread_service import (
    AttemptClaim,
    ThreadCreator,
    ThreadModelCatalog,
    ThreadService,
)
from .thread_worker import RuntimeFactory


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


@dataclass(frozen=True, slots=True)
class ThreadApplicationAssembly:
    """One application-owned pairing of model authority and runtime factory.

    A hosted process must receive both halves from the same application
    composition root.  Keeping them together prevents a model catalog from
    being paired accidentally with a runtime that cannot prepare that model
    context.  The assembly remains domain-neutral: the selected application
    supplies the Authority resolver and Pi session factory.
    """

    catalog: ThreadModelCatalog
    runtime_factory: RuntimeFactory

    def __post_init__(self) -> None:
        if not callable(getattr(self.catalog, "resolve", None)):
            raise TypeError("Thread application catalog must implement resolve")
        if not isinstance(getattr(self.catalog, "default_model_id", None), str):
            raise TypeError("Thread application catalog must declare default_model_id")
        if not callable(self.runtime_factory):
            raise TypeError("Thread application runtime_factory must be callable")

    @classmethod
    def from_authority(
        cls,
        *,
        default_model_id: str,
        model_resolver: Callable[[str], Mapping[str, Any]],
        session_factory: Callable[[AttemptClaim], PiPromptSession],
        runtime_mode: str = "capstone",
    ) -> "ThreadApplicationAssembly":
        """Build an assembly from application-owned Authority and Pi seams.

        ``model_resolver`` is the only Authority-facing input.  The neutral
        catalog copies and validates the registered model identity and
        revision; no Authority object or Domain Pack implementation crosses
        into the Thread store.  ``session_factory`` is likewise responsible
        for selecting the application's prepared Pi session for a claimed
        Attempt.
        """

        catalog = AuthorityThreadModelCatalog(
            default_model_id=default_model_id, resolver=model_resolver,
        )
        runtime_factory = ApplicationPiRuntimeFactory(
            session_factory, runtime_mode=runtime_mode,
        )
        return cls(catalog=catalog, runtime_factory=runtime_factory)

    def thread_creator(self, service: ThreadService) -> ThreadCreator:
        """Create the persistence adapter for this exact application pair."""

        return ThreadCreator(service, self.catalog)


__all__ = ["ApplicationPiRuntimeFactory", "ThreadApplicationAssembly"]
