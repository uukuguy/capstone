"""Closed application registration for the ordinary native conversation entry."""
from capability_agent.application.manifest import ApplicationManifest
from capability_agent.application.output import JsonOutputRenderer
from capability_agent.application.profile import (
    ApplicationProfile, CredentialScope, DataSharingPolicy, DomainBinding,
)
from capability_agent.application.reporting import GenericReportShell
from capability_agent.domain.manifest import PackManifest
from capability_agent.domain.profile import NativeDomainRuntimeProfile, NativeExecutionConfig

from .application_registry import ApplicationRegistry


class ConversationPolicy:
    def load(self) -> str:
        from .native_task_context import POLICY_TEXT
        return POLICY_TEXT


class ConversationGuides:
    def load(self) -> tuple:
        return ()

    def open(self, resource_id: str) -> dict:
        raise KeyError(resource_id)


class ConversationAcceptance:
    def cases(self) -> tuple:
        return ('ordinary-conversation',)


def build_enterprise_research_profile() -> ApplicationProfile:
    policy = ConversationPolicy()
    native = NativeDomainRuntimeProfile(PackManifest('native-conversation', '1.0.0', 'Native conversation'),
        NativeExecutionConfig('delegated_pi', 'capstone-pi-task-result/1'), policy, ConversationGuides())
    return ApplicationProfile(ApplicationManifest('enterprise-research', '1.0.0', 'Enterprise research and analysis',
        'capstone-application-context/1', 'capstone-application-result/1', 'capstone-artifact/1', 'core'),
        (DomainBinding('native-conversation', 'native', native, CredentialScope(), DataSharingPolicy()),),
        JsonOutputRenderer(), policy, GenericReportShell(), ConversationAcceptance())


def resolve_enterprise_research_profile() -> ApplicationProfile:
    registry = ApplicationRegistry()
    registry.register('enterprise-research', '1.0.0', build_enterprise_research_profile)
    return registry.resolve('enterprise-research', '1.0.0')
