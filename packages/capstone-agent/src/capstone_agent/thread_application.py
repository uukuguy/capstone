"""Application-owned composition helpers for the neutral Thread worker seam."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from .harness import (
    AttemptAdmission,
    HarnessPiClient,
    HarnessRuntime,
    HarnessRuntimeRegistry,
    PiPromptSession,
)
from .model_capability_context import (
    ModelCapabilityContextOwner,
    PreparedModelCapabilityContext,
)
from .model_capability import CapstoneModelCapabilityCatalog
from .thread_catalog import AuthorityThreadModelCatalog
from .thread_service import (
    AttemptClaim,
    ThreadCreator,
    ThreadCapabilityCatalog,
    ThreadModelCatalog,
    ThreadService,
)
from .thread_worker import RuntimeFactory
from .runtime_capabilities import RuntimeCapabilityRegistry
from .turn_router import DefaultTurnRouter, TurnRouter


def _unconfigured_runtime_factory(_claim: AttemptClaim) -> HarnessRuntime:
    raise TypeError("Thread application runtime factory is required")


class FamilyRuntimeFactory:
    """Dispatch Attempts to the application-registered family runtime."""

    def __init__(self, factories: Mapping[str, RuntimeFactory]) -> None:
        if not isinstance(factories, Mapping) or not factories:
            raise ValueError("runtime family registry must not be empty")
        normalized: dict[str, RuntimeFactory] = {}
        for family, factory in factories.items():
            if not isinstance(family, str) or not family or not callable(factory):
                raise ValueError("runtime family registration is invalid")
            if family in normalized:
                raise ValueError(f"duplicate runtime family: {family}")
            normalized[family] = factory
        self._factories = normalized

    def __call__(self, claim: AttemptClaim) -> HarnessRuntime:
        family = claim.model_context.implementation_family
        factory = self._factories.get(family)
        if factory is None:
            raise RuntimeError(f"implementation family is not registered: {family}")
        return factory(claim)


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
        runtime_capabilities: RuntimeCapabilityRegistry | None = None,
    ) -> None:
        if not callable(session_factory):
            raise TypeError("session_factory must be callable")
        if runtime_capabilities is not None and not isinstance(
            runtime_capabilities, RuntimeCapabilityRegistry,
        ):
            raise TypeError("runtime_capabilities must be a RuntimeCapabilityRegistry")
        self._session_factory = session_factory
        self._runtime_mode = runtime_mode
        self.runtime_capabilities = runtime_capabilities

    def __call__(self, claim: AttemptClaim) -> HarnessRuntime:
        return HarnessPiClient(
            self._session_factory(claim), runtime_mode=self._runtime_mode,
        )


class PreparedApplicationPiRuntimeFactory:
    """Borrow a Run-owned prepared context for one Pi Attempt.

    The session factory receives the exact immutable context snapshot and its
    prepared contributions.  Stopping the Attempt's session never closes the
    context; the owning Run must call ``ModelCapabilityContextOwner.close_run``
    after the context is no longer active.
    """

    def __init__(
        self,
        context_owner: ModelCapabilityContextOwner,
        session_factory: Callable[
            [AttemptClaim, PreparedModelCapabilityContext], PiPromptSession
        ],
        *,
        runtime_mode: str = "capstone",
        runtime_capabilities: RuntimeCapabilityRegistry | None = None,
    ) -> None:
        if not isinstance(context_owner, ModelCapabilityContextOwner):
            raise TypeError("context_owner must be a ModelCapabilityContextOwner")
        if not callable(session_factory):
            raise TypeError("session_factory must be callable")
        if runtime_capabilities is not None and not isinstance(
            runtime_capabilities, RuntimeCapabilityRegistry,
        ):
            raise TypeError("runtime_capabilities must be a RuntimeCapabilityRegistry")
        self._context_owner = context_owner
        self._session_factory = session_factory
        self._runtime_mode = runtime_mode
        self.runtime_capabilities = runtime_capabilities
        self.rollback_selection_on_failure = True

    def __call__(self, claim: AttemptClaim) -> HarnessRuntime:
        context = self._context_owner.prepare(claim)
        session = self._session_factory(claim, context)
        admission = getattr(session, "admit_attempt", None)
        return HarnessPiClient(
            session,
            runtime_mode=self._runtime_mode,
            admission=cast(AttemptAdmission, admission) if callable(admission) else None,
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
    runtime_factory: RuntimeFactory = _unconfigured_runtime_factory
    runtime_registry: HarnessRuntimeRegistry | None = None
    runtime_name: str = "pi"
    capability_catalog: ThreadCapabilityCatalog | None = None
    capability_context_owner: ModelCapabilityContextOwner | None = None
    runtime_capabilities: RuntimeCapabilityRegistry | None = None
    turn_router: TurnRouter | None = None
    ordinary_conversation_enabled: bool = True

    def __post_init__(self) -> None:
        if not callable(getattr(self.catalog, "resolve", None)):
            raise TypeError("Thread application catalog must implement resolve")
        if not isinstance(getattr(self.catalog, "default_model_id", None), str):
            raise TypeError("Thread application catalog must declare default_model_id")
        if self.runtime_registry is not None and not isinstance(
            self.runtime_registry, HarnessRuntimeRegistry,
        ):
            raise TypeError("Thread application runtime registry is invalid")
        if not isinstance(self.runtime_name, str) or not self.runtime_name.strip():
            raise TypeError("Thread application runtime name is invalid")
        if self.runtime_factory is _unconfigured_runtime_factory:
            if self.runtime_registry is None:
                raise TypeError("Thread application runtime factory is required")
            object.__setattr__(
                self, "runtime_factory",
                self.runtime_registry.resolve(self.runtime_name),
            )
        elif not callable(self.runtime_factory):
            raise TypeError("Thread application runtime_factory must be callable")
        elif self.runtime_registry is not None:
            selected_factory = self.runtime_registry.resolve(self.runtime_name)
            if self.runtime_factory is not selected_factory:
                raise ValueError(
                    "runtime factory conflicts with runtime registry selection",
                )
        if self.capability_context_owner is not None and not isinstance(
            self.capability_context_owner, ModelCapabilityContextOwner,
        ):
            raise TypeError("Thread application capability context owner is invalid")
        if self.runtime_capabilities is not None and not isinstance(
            self.runtime_capabilities, RuntimeCapabilityRegistry,
        ):
            raise TypeError("Thread application runtime capabilities are invalid")
        if self.turn_router is not None and not callable(getattr(self.turn_router, "plan", None)):
            raise TypeError("Thread application turn router is invalid")
        if type(self.ordinary_conversation_enabled) is not bool:
            raise TypeError("ordinary conversation policy is invalid")

    @classmethod
    def from_authority(
        cls,
        *,
        default_model_id: str,
        model_resolver: Callable[[str], Mapping[str, Any]],
        session_factory: Callable[[AttemptClaim], PiPromptSession],
        runtime_mode: str = "capstone",
        runtime_capabilities: RuntimeCapabilityRegistry | None = None,
        turn_router: TurnRouter | None = None,
        ordinary_conversation_enabled: bool = True,
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
            runtime_capabilities=runtime_capabilities,
        )
        runtime_registry = HarnessRuntimeRegistry()
        runtime_registry.register("pi", runtime_factory)
        return cls(
            catalog=catalog, runtime_factory=runtime_registry.resolve("pi"),
            runtime_registry=runtime_registry, runtime_name="pi",
            runtime_capabilities=runtime_capabilities, turn_router=turn_router,
            ordinary_conversation_enabled=ordinary_conversation_enabled,
        )

    @classmethod
    def from_composite_authority(
        cls,
        *,
        catalog: ThreadModelCatalog,
        runtime_factories: Mapping[str, RuntimeFactory],
        capability_catalog: ThreadCapabilityCatalog | None = None,
        runtime_capabilities: RuntimeCapabilityRegistry | None = None,
        turn_router: TurnRouter | None = None,
        ordinary_conversation_enabled: bool = True,
    ) -> "ThreadApplicationAssembly":
        """Build one application assembly over several family adapters.

        Each factory owns its Authority/Domain Pack environment.  The neutral
        worker sees only the family dispatcher and the immutable model context.
        Prepared multi-family Context owners can be layered by a caller when
        those environments share a compatible process boundary.
        """

        runtime_factory = FamilyRuntimeFactory(runtime_factories)
        runtime_registry = HarnessRuntimeRegistry()
        runtime_registry.register("pi", runtime_factory)
        return cls(
            catalog=catalog,
            runtime_factory=runtime_registry.resolve("pi"),
            runtime_registry=runtime_registry, runtime_name="pi",
            capability_catalog=capability_catalog,
            runtime_capabilities=runtime_capabilities, turn_router=turn_router,
            ordinary_conversation_enabled=ordinary_conversation_enabled,
        )

    @classmethod
    def from_prepared_authority(
        cls,
        *,
        default_model_id: str,
        model_resolver: Callable[[str], Mapping[str, Any]],
        model_catalog: ThreadModelCatalog | None = None,
        capability_catalog: CapstoneModelCapabilityCatalog,
        capability_context_owner: ModelCapabilityContextOwner,
        session_factory: Callable[
            [AttemptClaim, PreparedModelCapabilityContext], PiPromptSession
        ],
        runtime_mode: str = "capstone",
        runtime_capabilities: RuntimeCapabilityRegistry | None = None,
        turn_router: TurnRouter | None = None,
        ordinary_conversation_enabled: bool = True,
    ) -> "ThreadApplicationAssembly":
        """Pair model authority, exact Profile catalog, Context owner, and Pi."""

        if capability_context_owner.catalog is not capability_catalog:
            raise ValueError("capability catalog and context owner must be paired")
        if model_catalog is None:
            catalog = AuthorityThreadModelCatalog(
                default_model_id=default_model_id, resolver=model_resolver,
            )
        else:
            if model_catalog.default_model_id != default_model_id:
                raise ValueError("model catalog default does not match application default")
            if not callable(getattr(model_catalog, "resolve", None)):
                raise TypeError("model catalog must implement resolve")
            catalog = model_catalog
        runtime_factory = PreparedApplicationPiRuntimeFactory(
            capability_context_owner, session_factory, runtime_mode=runtime_mode,
            runtime_capabilities=runtime_capabilities,
        )
        runtime_registry = HarnessRuntimeRegistry()
        runtime_registry.register("pi", runtime_factory)
        return cls(
            catalog=catalog,
            runtime_factory=runtime_registry.resolve("pi"),
            runtime_registry=runtime_registry, runtime_name="pi",
            capability_catalog=capability_catalog,
            capability_context_owner=capability_context_owner,
            runtime_capabilities=runtime_capabilities, turn_router=turn_router,
            ordinary_conversation_enabled=ordinary_conversation_enabled,
        )

    def turn_router_for_worker(self) -> TurnRouter:
        """Return the application policy used by the hosted Thread worker."""

        return DefaultTurnRouter(
            decision_router=self.turn_router,
            ordinary_conversation_enabled=self.ordinary_conversation_enabled,
        )

    def thread_creator(self, service: ThreadService) -> ThreadCreator:
        """Create the persistence adapter for this exact application pair."""

        return ThreadCreator(service, self.catalog, self.capability_catalog)


__all__ = [
    "ApplicationPiRuntimeFactory",
    "FamilyRuntimeFactory",
    "PreparedApplicationPiRuntimeFactory",
    "HarnessRuntimeRegistry",
    "ThreadApplicationAssembly",
]
