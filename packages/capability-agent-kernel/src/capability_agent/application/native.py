"""Application-supplied native preparation, independent of any executor vendor."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from collections.abc import Mapping

from capability_agent.application.errors import ApplicationConfigurationError
from capability_agent.application.profile import ApplicationProfile, DomainBinding
from capability_agent.domain.profile import NativeDomainRuntimeProfile
from capability_agent.domain.provisioning import CredentialLease


@dataclass(frozen=True, slots=True)
class NativePreparationReceipt:
    resource_profile_id: str
    resource_revision: str
    result_contract: str
    executor_identity_digest: str
    required_resources: tuple[str, ...]

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value.strip() for value in (
            self.resource_profile_id, self.resource_revision, self.result_contract,
            self.executor_identity_digest,
        )):
            raise ValueError("native preparation identity must be nonempty text")
        if (not isinstance(self.required_resources, tuple)
                or any(not isinstance(value, str) or not value.strip() for value in self.required_resources)
                or len(set(self.required_resources)) != len(self.required_resources)):
            raise ValueError("native preparation resources must be unique immutable identities")


class PreparedNativeEndpoint(Protocol):
    @property
    def receipt(self) -> NativePreparationReceipt: ...

    def close(self) -> None: ...


class NativeBindingPreparer(Protocol):
    def prepare(
        self, *, binding: DomainBinding, profile: NativeDomainRuntimeProfile,
        workspace: Path, credentials: CredentialLease,
    ) -> PreparedNativeEndpoint: ...


@dataclass(frozen=True, slots=True)
class PreparedNativeBinding:
    binding: DomainBinding
    endpoint: PreparedNativeEndpoint
    receipt: NativePreparationReceipt


def require_authority_execution(
    profile: ApplicationProfile, prepared_bindings: Mapping[str, object] | None = None,
) -> None:
    """Reject unsupported native work before a legacy runner starts resources."""
    for binding in getattr(profile, "domains", ()):
        if prepared_bindings is not None and binding.binding_id not in prepared_bindings:
            continue
        if isinstance(getattr(binding, "profile", None), NativeDomainRuntimeProfile):
            raise ApplicationConfigurationError("native binding is not supported by the authority runner")
    if prepared_bindings is not None and any(
        isinstance(binding, PreparedNativeBinding) for binding in prepared_bindings.values()
    ):
        raise ApplicationConfigurationError("native binding is not supported by the authority runner")
