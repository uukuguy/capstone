"""Bind native Pack preparation to an already registered Pi executor host."""

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from capability_agent.application.errors import DomainProvisioningError
from capability_agent.application.native import NativePreparationReceipt
from capability_agent.application.profile import DomainBinding
from capability_agent.domain.profile import NativeDomainRuntimeProfile
from capability_agent.domain.provisioning import CredentialLease

from .general_executor_composition import _resource_profiles
from .pi_delegation import GeneralPiExecutor, _json_document


@dataclass(frozen=True, slots=True)
class PreparedPiResources:
    receipt: NativePreparationReceipt

    def close(self) -> None:
        # Preparation borrows the registered host; it does not own its lifetime.
        pass


class PiNativeBindingPreparer:
    def __init__(self, executor: GeneralPiExecutor) -> None:
        self._executor = executor

    def prepare(
        self, *, binding: DomainBinding, profile: NativeDomainRuntimeProfile,
        workspace: Path, credentials: CredentialLease,
    ) -> PreparedPiResources:
        del binding, workspace
        if credentials.credentials:
            raise DomainProvisioningError("native resources use host-owned credentials")
        execution = profile.execution
        if execution.result_contract != 'capstone-pi-task-result/1':
            raise DomainProvisioningError("native result contract is unsupported")
        try:
            capability = _json_document(self._executor.capability)
            identity = _json_document(self._executor.identity)
            profiles = capability.get('resource_profiles', {})
            _resource_profiles(profiles)
        except Exception:
            raise DomainProvisioningError("native resource publication is invalid") from None
        if (capability.get('capability_id') != 'general-pi'
                or capability.get('enabled') is not True
                or capability.get('available') is not True or not identity):
            raise DomainProvisioningError("native executor is unavailable")
        selected = profiles.get(execution.resource_profile_id)
        if selected is None:
            raise DomainProvisioningError("native resource profile is unavailable")
        resources = {resource['id']: resource for resource in selected['resources']}
        if len(resources) != len(selected['resources']):
            raise DomainProvisioningError("native resource identities are ambiguous")
        if any(resource_id not in resources or resources[resource_id]['ready'] is not True
               for resource_id in execution.required_resources):
            raise DomainProvisioningError("native required resource is unavailable")
        identity_digest = sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        return PreparedPiResources(NativePreparationReceipt(
            execution.resource_profile_id, selected['revision'], execution.result_contract,
            identity_digest, execution.required_resources,
        ))
