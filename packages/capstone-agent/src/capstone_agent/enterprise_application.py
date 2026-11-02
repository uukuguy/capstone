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


class GovernedResearchPolicy:
    def load(self) -> str:
        from .native_task_context import RESEARCH_POLICY_TEXT
        return RESEARCH_POLICY_TEXT


class SplitResearchPolicy:
    def load(self) -> str:
        from .native_task_context import SPLIT_RESEARCH_POLICY_TEXT
        return SPLIT_RESEARCH_POLICY_TEXT


class ReviewedResearchPolicy:
    def load(self) -> str:
        from .native_task_context import REVIEWED_RESEARCH_POLICY_TEXT
        return REVIEWED_RESEARCH_POLICY_TEXT


def build_governed_research_profile(version='1.1.0', *, policy_variant='default') -> ApplicationProfile:
    from enterprise_research import build_profile, ResearchAcceptance
    from .native_task_context import registered_research_policy
    entry = registered_research_policy(version, policy_variant)
    class RegisteredPolicy:
        def load(self) -> str:
            return entry.system_policy
    policy = RegisteredPolicy()
    return ApplicationProfile(ApplicationManifest('enterprise-research', version,
        'Enterprise research and analysis', 'capstone-application-context/1',
        'capstone-application-result/1', 'capstone-artifact/1', 'core'),
        (DomainBinding('research-methods', 'research', build_profile(entry.pack_version, variant=entry.variant), CredentialScope(), DataSharingPolicy()),),
        JsonOutputRenderer(), policy, GenericReportShell(), ResearchAcceptance())


def build_general_chat_profile() -> ApplicationProfile:
    return _build_native_profile('general-chat', 'General conversation', GeneralChatPolicy())


def resolve_native_profile(session_type: str | None, version: str | None = None, *, policy_variant='default') -> ApplicationProfile:
    selected = 'enterprise-research' if session_type is None else session_type
    if selected not in {'enterprise-research', 'general-chat'}:
        raise ValueError('native session type is not registered')
    if policy_variant != 'default':
        if selected != 'enterprise-research' or version is None:
            raise ValueError('native profile policy variant is not registered')
        return build_governed_research_profile(version, policy_variant=policy_variant)
    registry = ApplicationRegistry()
    registry.register('enterprise-research', '1.0.0', build_enterprise_research_profile)
    registry.register('enterprise-research', '1.1.0', build_governed_research_profile)
    registry.register('enterprise-research', '1.2.0', lambda: build_governed_research_profile('1.2.0'))
    registry.register('enterprise-research', '1.3.0', lambda: build_governed_research_profile('1.3.0'))
    registry.register('enterprise-research', '1.4.0', lambda: build_governed_research_profile('1.4.0'))
    registry.register('enterprise-research', '1.5.0', lambda: build_governed_research_profile('1.5.0'))
    registry.register('enterprise-research', '1.6.0', lambda: build_governed_research_profile('1.6.0'))
    registry.register('enterprise-research', '1.7.0', lambda: build_governed_research_profile('1.7.0'))
    registry.register('enterprise-research', '1.8.0', lambda: build_governed_research_profile('1.8.0'))
    registry.register('enterprise-research', '1.9.0', lambda: build_governed_research_profile('1.9.0'))
    registry.register('enterprise-research', '1.10.0', lambda: build_governed_research_profile('1.10.0'))
    registry.register('enterprise-research', '1.11.0', lambda: build_governed_research_profile('1.11.0'))
    registry.register('enterprise-research', '1.12.0', lambda: build_governed_research_profile('1.12.0'))
    registry.register('enterprise-research', '1.13.0', lambda: build_governed_research_profile('1.13.0'))
    registry.register('enterprise-research', '1.14.0', lambda: build_governed_research_profile('1.14.0'))
    registry.register('enterprise-research', '1.15.0', lambda: build_governed_research_profile('1.15.0'))
    registry.register('enterprise-research', '1.16.0', lambda: build_governed_research_profile('1.16.0'))
    registry.register('enterprise-research', '1.17.0', lambda: build_governed_research_profile('1.17.0'))
    registry.register('enterprise-research', '1.18.0', lambda: build_governed_research_profile('1.18.0'))
    registry.register('enterprise-research', '1.19.0', lambda: build_governed_research_profile('1.19.0'))
    registry.register('enterprise-research', '1.20.0', lambda: build_governed_research_profile('1.20.0'))
    registry.register('general-chat', '1.0.0', build_general_chat_profile)
    return registry.resolve(selected, version or '1.0.0')


def resolve_enterprise_research_profile() -> ApplicationProfile:
    return resolve_native_profile('enterprise-research')
