"""Structural contracts for injected application runtime seams.

These protocols describe the invocation shapes used by ``AgentApplication``.
They deliberately do not own concrete Kernel composition or Domain Pack types.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from capability_agent.application.composition import CredentialBroker
    from capability_agent.application.profile import ApplicationProfile
    from capability_agent.application.registry import DomainRegistry
    from capability_agent.application.runner import ApplicationRequest
    from capability_agent.application.workspace import ApplicationWorkspace
    from capability_agent.application.output import ValidatedDomainOutput
    from capability_agent.application.turns import ActiveTurnHandle, FinalizedTurn


SemanticEventObserver = Callable[[Mapping[str, object]], None]
HeartbeatObserver = Callable[[], None]


class ProviderSession(Protocol):
    """A provider transport that preserves every current-turn callback."""

    def start(self) -> None: ...

    def prompt_and_wait(
        self,
        question: str,
        *,
        on_semantic_event: SemanticEventObserver,
        correlation_id: str | None,
        on_heartbeat: HeartbeatObserver,
    ) -> str: ...

    def stop(self) -> None: ...


class LegacyPromptSession(Protocol):
    """Supported construction-time legacy spelling with the full prompt contract."""

    def start(self) -> None: ...

    def prompt(
        self,
        question: str,
        *,
        on_semantic_event: SemanticEventObserver,
        correlation_id: str | None,
        on_heartbeat: HeartbeatObserver,
    ) -> str: ...

    def stop(self) -> None: ...


class ProviderFactory(Protocol):
    """Create a provider from the runner's established five inputs."""

    def __call__(
        self,
        *,
        request: ApplicationRequest,
        profile: ApplicationProfile,
        prepared_application: "PreparedApplicationRuntime",
        bindings: Mapping[str, object],
        # Catalog fixtures are intentionally opaque to the runner; it only
        # forwards this value to the selected provider factory.
        catalog: object | None,
    ) -> ProviderSession: ...


class ApplicationPreparer(Protocol):
    """Prepare one application from its established assembly inputs."""

    def __call__(
        self,
        *,
        profile: ApplicationProfile,
        request: ApplicationRequest,
        workspace: ApplicationWorkspace | None,
        registry: DomainRegistry | None,
        credentials: CredentialBroker | None,
    ) -> "PreparedApplicationRuntime": ...


class PreparedApplicationRuntime(Protocol):
    """The only prepared-application surface consumed by the runner."""

    @property
    def bindings(self) -> Mapping[str, object]: ...


class TurnControllerSource(Protocol):
    """Construction-time controller operations for one application run."""

    def start(self, ordinal: int, instruction: str) -> ActiveTurnHandle: ...

    def submit(
        self,
        handle: ActiveTurnHandle,
        *,
        answer_output: str,
        answer_summary: str | None = None,
        referenced_bindings: tuple[str, ...],
        result_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        duration_seconds: float,
    ) -> FinalizedTurn: ...

    def fail(
        self, handle: ActiveTurnHandle, *, error: str, duration_seconds: float
    ) -> FinalizedTurn: ...


class TurnControllerSession(TurnControllerSource, Protocol):
    """Checked controller operations and descriptor runtime channels."""

    @property
    def active_turn_path(self) -> Path | None: ...

    @property
    def context_view_path(self) -> Path | None: ...

    @property
    def trajectory_requests_path(self) -> Path | None: ...

    @property
    def trajectory_capture_state_path(self) -> Path | None: ...

    @property
    def trajectory_allowed_refs_path(self) -> Path | None: ...

    @property
    def trajectory_acks_path(self) -> Path | None: ...


class DomainOutputBuilder(Protocol):
    """Build one selected Domain Pack output after committed answers exist."""

    def __call__(
        self,
        *,
        binding_id: str,
        binding: object | None,
        context: object | None,
        committed_answers: tuple[FinalizedTurn, ...],
        report_ref: str | None,
    ) -> ValidatedDomainOutput: ...


class StateContextAdapter(Protocol):
    """Build a Domain Pack presentation context from its current state."""

    def build_context(self, *, binding_id: str, state: object) -> object: ...


class DomainPayloadBuilder(Protocol):
    """Build a selected Domain Pack payload after answer commit."""

    def build(
        self,
        *,
        binding_id: str,
        context: object | None,
        committed_answers: tuple[FinalizedTurn, ...],
    ) -> Mapping[str, object]: ...


class OutputValidator(Protocol):
    """Validate a selected output against its current-run context."""

    def validate(self, payload: Mapping[str, object], *, context: object | None) -> None: ...


class ReportPublisher(Protocol):
    """Derived report publication after configuration ingress adaptation."""

    def prepare(
        self, *, questions: tuple[str, ...], workspace: ApplicationWorkspace
    ) -> None: ...

    def render(
        self,
        *,
        questions: tuple[str, ...],
        answers: tuple[str, ...],
        assurances: tuple[str, ...],
        trajectories: tuple[str, ...],
        references: tuple[str, ...],
        context: object | None,
        presentation: object | None,
        core: Mapping[str, object],
        domains: Mapping[str, object],
        workspace: ApplicationWorkspace,
        runtime: Mapping[str, object],
    ) -> str: ...


__all__ = [
    "ApplicationPreparer",
    "DomainPayloadBuilder",
    "DomainOutputBuilder",
    "HeartbeatObserver",
    "LegacyPromptSession",
    "PreparedApplicationRuntime",
    "OutputValidator",
    "ProviderFactory",
    "ProviderSession",
    "ReportPublisher",
    "SemanticEventObserver",
    "StateContextAdapter",
    "TurnControllerSession",
    "TurnControllerSource",
]
