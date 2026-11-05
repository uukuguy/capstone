"""Native Thread worker using the shared ledger, lease loop, and Pi runtime.

This process has no Authority or professional model catalog. The isolated Pi
host retains its existing private control and Provider transport boundaries.
"""
import os
import threading
import re
from collections.abc import Mapping
from pathlib import Path

from .general_executor_composition import configured_general_executor
from .intent_runtime import IntentRuntimeFactory
from .thread_service import PostgresThreadService
from .thread_worker import serve_thread_attempts
from .worker_wake import create_wake_app


def native_worker_capacity(environment: Mapping[str, str]) -> int:
    value = environment.get('CAPSTONE_NATIVE_MAX_CONCURRENT_ATTEMPTS', '1')
    if not re.fullmatch(r'[1-9][0-9]*', value):
        raise ValueError('CAPSTONE_NATIVE_MAX_CONCURRENT_ATTEMPTS must be a positive integer')
    return int(value)


def native_runtime_factory(executor, *, research_root: Path | None = None,
                           environment=None, recognizer_factory=None,
                           unscoped_intent: bool = False, business_factory=None):
    environment = os.environ if environment is None else environment
    from .application_capacity import limits
    research_timeout = environment.get('CAPSTONE_ENTERPRISE_RESEARCH_TIMEOUT_SECONDS')
    def unavailable(*args):
        raise RuntimeError('professional execution is not registered on this worker')
    unavailable.domain_execution = False
    business = unavailable if business_factory is None else business_factory
    factory = IntentRuntimeFactory(business, recognizer_factory or unavailable, unavailable,
                                   general_executor=executor,
                                   general_timeout_seconds=float(environment.get(
                                       'CAPSTONE_THREAD_ATTEMPT_TIMEOUT_SECONDS', str(limits.execution_seconds))),
                                   application_timeout_seconds={'enterprise-research': float(research_timeout)
                                       if research_timeout else limits.research_execution_seconds},
                                   unscoped_intent=unscoped_intent)
    factory.native_research_root = research_root
    return factory


def application_root() -> Path:
    candidate = Path(__file__).resolve().parents[4]
    if (candidate / 'configs' / 'runtime').is_dir():
        return candidate
    packaged = Path('/app')
    if (packaged / 'configs' / 'runtime').is_dir():
        return packaged
    raise RuntimeError('native intent configuration root is unavailable')


def native_intent_policy_path(profile, workspace: Path) -> Path:
    """Persist the application policy. A native pack manifest has no policy file."""
    text = profile.application_policy.load()
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError('native intent policy is unavailable')
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    path = workspace / 'system-policy.md'
    path.write_text(text, encoding='utf-8')
    return path


def build_native_unscoped_recognizer(workspace_root: Path, environment=None):
    """Build the in-process intent recognizer. Business execution stays unregistered."""
    from .enterprise_application import resolve_native_profile
    from .pi_intent import NativeConversationPiSessionBuilder, PiIntentRecognizer
    from .runtime import build_runtime_host, load_runtime_environment, resolve_harness_llm, resolve_recognition_llm
    root = application_root()
    selected = load_runtime_environment(root, os.environ if environment is None else environment)
    profile = resolve_native_profile('enterprise-research', '1.20.0')
    workspace = Path(workspace_root)
    host = build_runtime_host(root, profile, selected,
                              system_policy_path=native_intent_policy_path(profile, workspace))
    def for_attempt(claim=None):
        selection = None if claim is None else (claim.submission or {}).get('llm_selection')
        execution = resolve_harness_llm(root, selected, workbench_selection=selection)
        llm = resolve_recognition_llm(root, selected,
            execution)
        reasoning = None
        if (selected.get('CAPSTONE_RUNTIME_PROFILE') == 'capstone-workbench-v1'
                and (selection is not None or (
                    selected.get('CAPSTONE_PUBLIC_PROVIDER') == 'openai-compatible'
                    and not selected.get('CAPABILITY_AGENT_LLM_PROVIDER')))):
            from .workbench_llm_profiles import ProfileRegistry
            registry = ProfileRegistry(root / 'configs/runtime/workbench-llm-profiles.json', environment=selected)
            registered = registry.resolve(selection if selection is not None else registry.freeze())
            if (llm.config.provider == execution.config.provider
                    and llm.config.pi_provider == execution.config.pi_provider
                    and llm.config.model == registered['model']
                    and llm.config.base_url.rstrip('/') == registered['base_url'].rstrip('/')):
                reasoning = registered.get('reasoning')
        builder = NativeConversationPiSessionBuilder(
            runtime_host=host, resolved_llm=llm, workspace_root=workspace,
            base_environment=selected, model_reasoning=reasoning)
        return PiIntentRecognizer(builder.build_intent, builder.identity)

    def factory():
        return for_attempt()

    factory.for_attempt = for_attempt
    return factory


def lazy_native_unscoped_recognizer(workspace_root: Path, environment=None):
    """Load the legacy recognizer only when an accepted input requires it."""
    def for_attempt(claim=None):
        return build_native_unscoped_recognizer(workspace_root, environment).for_attempt(claim)

    def factory():
        return for_attempt()

    factory.for_attempt = for_attempt
    return factory


def main() -> int:
    import uvicorn
    from .hosting import load_host_settings, build_artifacts
    from .ledger import Ledger
    settings = load_host_settings(os.environ)
    capacity = native_worker_capacity(os.environ)
    executor = configured_general_executor(os.environ)
    if executor is None:
        raise RuntimeError('native conversation executor is not configured')
    service = PostgresThreadService(settings.database_url)
    service.initialize()
    from .session_title_summary import TitleSummaryScheduler
    title_scheduler = TitleSummaryScheduler()
    setattr(service, '_title_summary_scheduler', title_scheduler)
    service.set_material_store(build_artifacts(settings, Ledger(settings.database_url)).store)
    service.set_native_executor(executor)
    factory = native_runtime_factory(
        executor, research_root=settings.runs_root / 'native-research',
        recognizer_factory=lazy_native_unscoped_recognizer(settings.runs_root / 'native-intent'))
    stop, wake = threading.Event(), threading.Event()
    scheduler = threading.Thread(target=serve_thread_attempts, kwargs={
        'service': service, 'runtime_factory': factory,
        'worker_id': 'capstone-native-worker', 'implementation_family': 'native',
        'max_concurrent_attempts': capacity,
        'wake_event': wake, 'stop_event': stop}, daemon=True, name='capstone-native-worker')
    scheduler.start()
    try:
        uvicorn.run(create_wake_app(wake, settings.operator_token,
            implementation_family='native', input_catalog=service.input_catalog,
            thread_family=lambda _: 'native', health_check=scheduler.is_alive),
            host=settings.bind_host, port=settings.port, access_log=False)
    finally:
        title_scheduler.pool.shutdown(wait=False, cancel_futures=True)
        stop.set()
        wake.set()
        scheduler.join(timeout=5)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
