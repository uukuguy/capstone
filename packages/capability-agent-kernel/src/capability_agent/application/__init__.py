"""Application-neutral runtime preparation."""

from capability_agent.application.composition import (
    PreparedDomainRuntime,
    prepare_domain_runtime,
)

__all__ = ["PreparedDomainRuntime", "prepare_domain_runtime"]
