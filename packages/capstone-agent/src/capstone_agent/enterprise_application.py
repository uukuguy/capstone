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


class GeneralChatPolicy:
    def load(self) -> str:
        from .native_task_context import GENERAL_CHAT_POLICY_TEXT
        return GENERAL_CHAT_POLICY_TEXT


class ConversationGuides:
    def load(self) -> tuple:
        return ()

    def open(self, resource_id: str) -> dict:
        raise KeyError(resource_id)


class ConversationAcceptance:
    def cases(self) -> tuple:
        return ('ordinary-conversation',)


def _build_native_profile(application_id, title, policy) -> ApplicationProfile:
    native = NativeDomainRuntimeProfile(PackManifest('native-conversation', '1.0.0', 'Native conversation'),
        NativeExecutionConfig('delegated_pi', 'capstone-pi-task-result/1'), policy, ConversationGuides())
    return ApplicationProfile(ApplicationManifest(application_id, '1.0.0', title,
        'capstone-application-context/1', 'capstone-application-result/1', 'capstone-artifact/1', 'core'),
        (DomainBinding('native-conversation', 'native', native, CredentialScope(), DataSharingPolicy()),),
        JsonOutputRenderer(), policy, GenericReportShell(), ConversationAcceptance())


def build_enterprise_research_profile() -> ApplicationProfile:
    return _build_native_profile('enterprise-research', 'Enterprise research and analysis', ConversationPolicy())


def build_general_chat_profile() -> ApplicationProfile:
    return _build_native_profile('general-chat', 'General conversation', GeneralChatPolicy())


def resolve_native_profile(session_type: str | None) -> ApplicationProfile:
    selected = 'enterprise-research' if session_type is None else session_type
    if selected not in {'enterprise-research', 'general-chat'}:
        raise ValueError('native session type is not registered')
    registry = ApplicationRegistry()
    registry.register('enterprise-research', '1.0.0', build_enterprise_research_profile)
    registry.register('general-chat', '1.0.0', build_general_chat_profile)
    return registry.resolve(selected, '1.0.0')


def resolve_enterprise_research_profile() -> ApplicationProfile:
    return resolve_native_profile('enterprise-research')
