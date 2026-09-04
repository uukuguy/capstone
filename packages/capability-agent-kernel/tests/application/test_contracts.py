from __future__ import annotations

from dataclasses import replace

import pytest

from capability_agent import (
    AcceptanceProfile,
    AnswerCommitError,
    AnswerEvidencePolicy,
    ApplicationConfigurationError,
    ApplicationManifest,
    ApplicationPolicy,
    ApplicationProfile,
    AuthorityIntegrityError,
    CapabilityRoutingError,
    CapabilityTransportError,
    CredentialScope,
    DataSharingPolicy,
    DomainAcceptanceProfile,
    DomainBinding,
    DomainOutputContract,
    DomainPolicyProvider,
    DomainProjectionError,
    DomainProvisioningError,
    DomainRegistrationError,
    DomainRuntimeProvisioner,
    DomainStateAdapter,
    GuideProvider,
    OutputRenderer,
    PolicyConflictError,
    PresentationError,
    PresentationProvider,
    ReportShell,
)


def _manifest() -> ApplicationManifest:
    return ApplicationManifest(
        application_id="inventory-agent",
        version="1.0.0",
        display_name="Inventory Agent",
        context_schema="application-context/1.0",
        result_schema="capability-agent-output/1.0",
        artifact_schema="capability-agent-run/1.0",
        core_tool_namespace="agent_",
    )


def _complete_domain_profile(inventory_profile):
    profile, _ = inventory_profile
    component = object()
    return replace(
        profile,
        provisioner=component,
        state_adapter=component,
        answer_policy=component,
        answer_admission_policy_factory=lambda authority: component,
        policy_provider=component,
        guide_provider=component,
        presentation_provider=component,
        output_contract=component,
        acceptance_profile=component,
    )


def _binding(inventory_profile, *, binding_id: str = "inventory", tool_namespace: str = "inventory_") -> DomainBinding:
    return DomainBinding(
        binding_id=binding_id,
        tool_namespace=tool_namespace,
        profile=_complete_domain_profile(inventory_profile),
        credential_scope=CredentialScope(),
        sharing_policy=DataSharingPolicy(),
    )


def _profile(inventory_profile, domains: tuple[DomainBinding, ...]) -> ApplicationProfile:
    placeholder = object()
    return ApplicationProfile(
        manifest=_manifest(),
        domains=domains,
        output_renderer=placeholder,
        application_policy=placeholder,
        report_shell=placeholder,
        acceptance_profile=placeholder,
    )


def test_application_profile_rejects_incomplete_fixture(inventory_profile) -> None:
    domain_profile, _ = inventory_profile
    binding = DomainBinding(
        binding_id="inventory",
        tool_namespace="inventory_",
        profile=domain_profile,
        credential_scope=CredentialScope(),
        sharing_policy=DataSharingPolicy(),
    )

    with pytest.raises(
        ApplicationConfigurationError, match="missing application components"
    ):
        _profile(inventory_profile, (binding,))


def test_domain_runtime_profile_reports_missing_components(inventory_profile) -> None:
    domain_profile, _ = inventory_profile

    assert domain_profile.missing_application_components() == (
        "provisioner",
        "state_adapter",
        "answer_policy",
        "answer_admission_policy_factory",
        "policy_provider",
        "guide_provider",
        "presentation_provider",
        "output_contract",
        "acceptance_profile",
    )
    assert _complete_domain_profile(inventory_profile).missing_application_components() == ()


def test_application_profile_accepts_one_complete_binding(inventory_profile) -> None:
    binding = _binding(inventory_profile)

    profile = _profile(inventory_profile, (binding,))

    assert profile.domains == (binding,)
    assert profile.domains[0].credential_scope == CredentialScope()
    assert profile.domains[0].sharing_policy == DataSharingPolicy(mode="deny")


@pytest.mark.parametrize("count", [0, 2])
def test_application_profile_requires_exactly_one_binding(
    inventory_profile, count: int
) -> None:
    bindings = tuple(
        _binding(
            inventory_profile,
            binding_id=f"inventory-{index}",
            tool_namespace=f"inventory_{index}_",
        )
        for index in range(count)
    )

    with pytest.raises(ApplicationConfigurationError, match="exactly one"):
        _profile(inventory_profile, bindings)


@pytest.mark.parametrize(
    ("field", "values"),
    [
        ("binding", ("inventory", "inventory")),
        ("tool namespace", ("inventory_", "inventory_")),
    ],
)
def test_application_profile_rejects_duplicate_binding_namespaces(
    inventory_profile, field: str, values: tuple[str, str]
) -> None:
    binding_ids = values if field == "binding" else ("inventory-a", "inventory-b")
    tool_namespaces = values if field == "tool namespace" else ("inventory_a_", "inventory_b_")
    bindings = tuple(
        _binding(
            inventory_profile,
            binding_id=binding_ids[index],
            tool_namespace=tool_namespaces[index],
        )
        for index in range(2)
    )

    with pytest.raises(ApplicationConfigurationError, match=f"duplicate {field}"):
        _profile(inventory_profile, bindings)


def test_all_application_contracts_and_error_categories_are_public() -> None:
    public_contracts = (
        ApplicationManifest,
        ApplicationProfile,
        DomainBinding,
        CredentialScope,
        DataSharingPolicy,
        ApplicationPolicy,
        ReportShell,
        AcceptanceProfile,
        OutputRenderer,
        DomainRuntimeProvisioner,
        DomainStateAdapter,
        AnswerEvidencePolicy,
        DomainPolicyProvider,
        GuideProvider,
        PresentationProvider,
        DomainOutputContract,
        DomainAcceptanceProfile,
    )
    public_errors = (
        ApplicationConfigurationError,
        DomainRegistrationError,
        DomainProvisioningError,
        CapabilityRoutingError,
        CapabilityTransportError,
        AuthorityIntegrityError,
        DomainProjectionError,
        PolicyConflictError,
        AnswerCommitError,
        PresentationError,
    )

    assert all(item.__module__.startswith("capability_agent.") for item in public_contracts)
    assert all(issubclass(error, Exception) for error in public_errors)
