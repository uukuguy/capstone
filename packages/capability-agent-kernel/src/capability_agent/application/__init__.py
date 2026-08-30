"""Application composition and output contracts."""

from capability_agent.application.composition import (
    PreparedApplication,
    PreparedBinding,
    PreparedDomainRuntime,
    prepare_application,
    prepare_domain_runtime,
)
from capability_agent.application.context_models import (
    APPLICATION_CONTEXT_EVENT_SCHEMA,
    APPLICATION_CONTEXT_SCHEMA,
    ApplicationContext,
    ContextEvent,
    ContextEventDraft,
    CoreContext,
    DomainStateEnvelope,
    canonical_state_hash,
)
from capability_agent.application.context_reducer import (
    ContextTransitionError,
    initial_context,
    reduce_context,
)
from capability_agent.application.context_store import ApplicationContextStore, ContextStoreError
from capability_agent.application.errors import (
    AnswerCommitError,
    ApplicationConfigurationError,
    AuthorityIntegrityError,
    CapabilityAgentError,
    CapabilityRoutingError,
    CapabilityTransportError,
    DomainProjectionError,
    DomainProvisioningError,
    DomainRegistrationError,
    PolicyConflictError,
    PresentationError,
)
from capability_agent.application.manifest import ApplicationManifest
from capability_agent.application.output import (
    ApplicationResult,
    BindingIdentity,
    BoundDomainOutput,
    CoreRunResult,
    FrameworkOutputComposer,
    JsonOutputRenderer,
    OutputRenderer,
    ValidatedDomainOutput,
)
from capability_agent.application.projector import (
    ApplicationInvocationProjector,
    ProjectionOutcome,
)
from capability_agent.application.profile import (
    AcceptanceProfile,
    ApplicationPolicy,
    ApplicationProfile,
    CredentialScope,
    DataSharingPolicy,
    DomainBinding,
    ReportShell,
)
from capability_agent.application.registry import DomainProfileFactory, DomainRegistry
from capability_agent.application.workspace import ApplicationWorkspace, WorkspaceError
from capability_agent.application.reporting import GenericReportShell
from capability_agent.application.runner import (
    AgentApplication,
    ApplicationOutcome,
    ApplicationRequest,
    ProviderSession,
)
from capability_agent.application.turns import (
    ActiveTurnHandle,
    ActiveTurnInProgressError,
    FinalizedTurn,
    StaleAnswerDraftError,
    TurnController,
)

__all__ = [
    "AcceptanceProfile",
    "APPLICATION_CONTEXT_EVENT_SCHEMA",
    "APPLICATION_CONTEXT_SCHEMA",
    "AnswerCommitError",
    "ApplicationConfigurationError",
    "ApplicationContext",
    "ApplicationContextStore",
    "ApplicationInvocationProjector",
    "ApplicationManifest",
    "ApplicationPolicy",
    "ApplicationProfile",
    "ApplicationResult",
    "ApplicationWorkspace",
    "ActiveTurnHandle",
    "ActiveTurnInProgressError",
    "AuthorityIntegrityError",
    "BindingIdentity",
    "BoundDomainOutput",
    "CapabilityAgentError",
    "CapabilityRoutingError",
    "CapabilityTransportError",
    "ContextEvent",
    "ContextEventDraft",
    "ContextStoreError",
    "ContextTransitionError",
    "CoreContext",
    "CoreRunResult",
    "CredentialScope",
    "DataSharingPolicy",
    "DomainBinding",
    "DomainProfileFactory",
    "DomainProjectionError",
    "DomainProvisioningError",
    "DomainRegistrationError",
    "DomainRegistry",
    "DomainStateEnvelope",
    "FrameworkOutputComposer",
    "GenericReportShell",
    "JsonOutputRenderer",
    "OutputRenderer",
    "PolicyConflictError",
    "PreparedApplication",
    "PreparedBinding",
    "PreparedDomainRuntime",
    "AgentApplication",
    "ApplicationOutcome",
    "ApplicationRequest",
    "ProviderSession",
    "ProjectionOutcome",
    "PresentationError",
    "ReportShell",
    "FinalizedTurn",
    "StaleAnswerDraftError",
    "TurnController",
    "ValidatedDomainOutput",
    "WorkspaceError",
    "canonical_state_hash",
    "initial_context",
    "prepare_application",
    "prepare_domain_runtime",
    "reduce_context",
]
