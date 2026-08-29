"""Domain-neutral application error categories."""


class CapabilityAgentError(RuntimeError):
    """Base error for application composition and execution failures."""


class ApplicationConfigurationError(CapabilityAgentError):
    """The application profile is incomplete or inconsistent."""


class DomainRegistrationError(CapabilityAgentError):
    """A domain registration is missing, incompatible, or conflicting."""


class DomainProvisioningError(CapabilityAgentError):
    """A safe endpoint or credential lease could not be prepared."""


class CapabilityRoutingError(CapabilityAgentError):
    """A capability cannot be routed to its declared binding."""


class CapabilityTransportError(CapabilityAgentError):
    """A bounded capability transport operation failed."""


class AuthorityIntegrityError(CapabilityAgentError):
    """A result or evidence reference failed authority verification."""


class DomainProjectionError(CapabilityAgentError):
    """A verified result could not be projected into domain state."""


class PolicyConflictError(CapabilityAgentError):
    """Kernel, application, domain, or sharing policies conflict."""


class AnswerCommitError(CapabilityAgentError):
    """A final answer cannot be committed with its declared references."""


class PresentationError(CapabilityAgentError):
    """A context or report presentation could not be produced."""


__all__ = [
    "AnswerCommitError",
    "ApplicationConfigurationError",
    "AuthorityIntegrityError",
    "CapabilityAgentError",
    "CapabilityRoutingError",
    "CapabilityTransportError",
    "DomainProjectionError",
    "DomainProvisioningError",
    "DomainRegistrationError",
    "PolicyConflictError",
    "PresentationError",
]
