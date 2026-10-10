"""Retained installation lifecycle through real preparation, builder and Authority."""
from dataclasses import replace
import json
import os
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from capstone_agent.runtime_resources import content_hash
from capstone_agent.thread_input_catalog import PreparedResourceCatalog, catalog_provider
from capstone_agent.thread_protocol import ModelContextSnapshot
from capstone_agent.thread_service import InMemoryThreadService
from capstone_agent.turn_router import TurnPlan
from grid_agent import hosted

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def retained_pair():
    managed = ROOT / '.grid-agent/runtime/agent-resources'
    original = (managed / 'current.json').read_bytes()
    a = json.loads(original)
    target = managed / 'installs' / uuid4().hex
    try:
        # Hard links retain verified immutable bytes. Only our copied descriptor
        # is unlinked and replaced. No original file or runtime is modified.
        def copy(source, destination):
            return shutil.copy2(source, destination) if 'private' in Path(source).parts else os.link(source, destination)
        shutil.copytree(managed / a['install_id'], target, copy_function=copy, symlinks=True)
        path = target / 'prepared-mcp.json'
        descriptor = json.loads(path.read_text())
        descriptor['install_id'] = 'installs/' + target.name
        path.unlink()
        path.write_text(json.dumps(descriptor))
        b = {'schema': 'capstone-resource-installation/1', 'install_id': descriptor['install_id'],
             'descriptor_sha256': content_hash(descriptor)}
        from capstone_agent.resource_installation import private_environment
        # Warm only this fixture's cold import caches before normal bounded inspection.
        subprocess.run([str(target / 'venv/bin/python'), '-I', '-B', '-c',
            'import pandapower,networkx,powerio,powermcp,mcp.server.mcpserver'],
            env=private_environment(target / 'private'), capture_output=True, check=True, timeout=180)
        yield managed, a, b
    finally:
        (managed / 'current.json').write_bytes(original)
        if target.exists():
            shutil.rmtree(target)


@pytest.mark.skipif(os.environ.get('CAPSTONE_POWERMCP_TESTS') != '1', reason='explicit retained real Authority check')
def test_pending_start_retry_and_new_task_keep_exact_prepared_backend(monkeypatch, tmp_path, retained_pair):
    from capstone_agent.resource_installation import inspect_installation
    from capstone_agent.kernel_pi_session import PreparedKernelPiSessionFactory, PreparedKernelPiRpcSessionBuilder
    from capability_agent.runtime.environment import RuntimeHost
    from capability_agent.runtime.lock import PiCommand, PiRuntimeIdentity
    from capability_agent.runtime.models import ResolvedLLM, ResolvedLLMConfig
    from capstone_agent.thread_input_catalog import prepared_bindings
    managed, a, b = retained_pair
    pointer = managed / 'current.json'
    original = pointer.read_bytes()
    assert inspect_installation(managed, install_id=b['install_id'], expected_descriptor_sha256=b['descriptor_sha256'])[0]
    monkeypatch.setenv('CAPSTONE_RUNS_ROOT', str(tmp_path / 'runs'))
    monkeypatch.setenv('CAPSTONE_POWERMCP_MANAGED_ROOT', str(managed))
    monkeypatch.setattr(hosted, 'select_validation_builder', lambda *_args: lambda *_args: None)
    assembly = hosted.build_registered_pandapower_thread_application()
    initial = assembly.catalog.resolve('ieee39')
    selected = assembly.capability_catalog.resolve(initial)
    model = ModelContextSnapshot('ctx_retained', initial.model_id, initial.model_revision,
        initial.implementation_family, 'sel_0', selected.enabled_profiles)
    service = InMemoryThreadService.from_document({'schema': 'capstone-thread-snapshot/1', 'thread_id': 'thr_retained',
        'run': {'run_id': 'run_retained', 'state': 'open'}, 'active_model_context': model.to_document(),
        'active_grid_page_id': 'page_ieee39', 'current_attempt': None, 'last_event_seq': 0, 'base_event_seq': 0},
        model_catalog=assembly.catalog, capability_catalog=assembly.capability_catalog)
    owner = assembly.capability_context_owner
    service.set_input_catalog_provider(catalog_provider(service,
        PreparedResourceCatalog(owner, None, ROOT / 'configs/runtime'), family_available=lambda _: True))
    def submit(identity, profile):
        return service.submit_command({'schema': 'capstone-command/1', 'thread_id': 'thr_retained',
            'command_id': 'cmd_' + identity, 'idempotency_key': 'idem_' + identity, 'kind': 'send_professional',
            'expected_event_seq': service.snapshot('thr_retained').last_event_seq,
            'payload': {'text': 'Audit this model', 'input': {'kind': 'skill_invocation', 'text': 'Audit this model',
                'skill_id': 'powerskills-pandapower', 'skill_version': profile['resources'][0]['version']},
                'resource_profile': {'profile_id': 'harness_engine', 'revision': profile['revision']}}})
    captured = []
    class Client:
        command = None
        def __init__(self, launch, *args, **kwargs):
            captured.append(launch)
        def start(self): pass
        def stop(self): pass
        def prompt_and_wait(self, *args, **kwargs): pass
    monkeypatch.setattr('capstone_agent.kernel_pi_session.PiRpcClient', Client)
    def build(current, prepared, profiles):
        policy = profiles[0].profile.domains[0].profile.manifest.system_policy_path
        host = RuntimeHost(command=PiCommand(('controlled',), PiRuntimeIdentity(path=tmp_path / 'model',
            source='fixture', package_version='1', lock_sha256='fixed')), project_pi_dir=tmp_path / 'pi',
            extension_path=ROOT / 'packages/pi-capability-tools', system_policy_path=policy)
        resolved = ResolvedLLM(ResolvedLLMConfig(provider='fixture', model='fixture', base_url='http://127.0.0.1/v1',
            auth_kind='none', credential_reference='FIXTURE_KEY', timeout_seconds=60, max_retries=0,
            pi_provider='fixture', compatibility_profile='generic', descriptor_version='fixture', public_headers={},
            field_sources={}, supports_tools=True), None)
        return PreparedKernelPiRpcSessionBuilder(runtime_host=host, resolved_llm=resolved,
            base_environment={'PATH': os.environ['PATH']})(current, prepared, profiles)
    def prepare_and_verify(current, identity):
        current = replace(current, turn_plan=TurnPlan(current.attempt.turn_id, current.attempt.attempt_id,
            'professional', 'fixture', '1', None, {}))
        prepared = owner.acquire(current)
        try:
            session = PreparedKernelPiSessionFactory(build)(current, prepared)
            assert captured[-1].environment['CAPSTONE_POWERMCP_INSTALL_ID'] == identity['install_id']
            assert captured[-1].environment['CAPSTONE_POWERMCP_DESCRIPTOR_SHA256'] == identity['descriptor_sha256']
            binding = prepared_bindings(prepared)['grid']
            from capability_agent.tools.guide import GuideIndex
            guide = GuideIndex.load(binding.runtime.guide_root_path).open('powerskills-pandapower-adapter')
            assert guide.text == current.submission['professional_resource']['guide']['text']
            described = binding.runtime.executor.invoke('analysis.operation.describe', {'operation': 'diagnostic.structural'})
            assert described['availability']['descriptor_sha256'] == identity['descriptor_sha256']
            context_ref = prepared.contributions[0].prepared.model_binding.context_ref
            result = binding.runtime.executor.invoke('analysis.run', {'context_ref': context_ref,
                'operation': 'diagnostic.structural', 'options': {}})
            assert result['summary']['provenance']['descriptor_sha256'] == identity['descriptor_sha256']
            assert result['revision_ref'] == model.model_revision
            assert binding.runtime.authority.verify_result(result['result_ref']).document['revision_ref'] == model.model_revision
            session.stop()
            return prepared
        finally:
            owner.release(prepared)
    try:
        profile_a = service.input_catalog('thr_retained')['resource_profiles']['harness_engine']
        assert submit('a', profile_a).status == 'accepted'
        # Publication occurs before the first claim/preparation of the accepted task.
        pointer.write_text(json.dumps(b))
        first = service.claim_attempt('worker', 180)
        frozen = json.loads(json.dumps(first.submission))
        assert frozen['professional_resource']['installation_id'] == a['install_id']
        prepared_a = prepare_and_verify(replace(first, submission=frozen), a)
        service.finish_attempt(first, phase='failed', payload={})
        retry = {'schema': 'capstone-command/1', 'thread_id': 'thr_retained', 'kind': 'retry_new_attempt',
            'command_id': 'cmd_retry', 'idempotency_key': 'idem_retry',
            'expected_event_seq': service.snapshot('thr_retained').last_event_seq,
            'payload': {'attempt_id': first.attempt.attempt_id}}
        assert service.submit_command(retry).status == 'accepted'
        repeated = service.claim_attempt('worker', 180)
        assert prepare_and_verify(repeated, a) is prepared_a
        service.finish_attempt(repeated, phase='failed', payload={})
        profile_b = service.input_catalog('thr_retained')['resource_profiles']['harness_engine']
        assert profile_b['revision'] != profile_a['revision']
        assert submit('b', profile_b).status == 'accepted'
        latest = service.claim_attempt('worker', 180)
        assert prepare_and_verify(latest, b) is not prepared_a
        assert not prepared_a.closed
        from capstone_agent.professional_resources import restore_harness_selection
        installed_b = managed / b['install_id']
        missing_b = installed_b.with_name('.missing-' + installed_b.name)
        installed_b.rename(missing_b)
        try:
            with pytest.raises(ValueError, match='unavailable'):
                restore_harness_selection(ROOT / 'configs/runtime', latest.submission['professional_resource'])
        finally:
            missing_b.rename(installed_b)
        owner.close()
        assert prepared_a.closed
        # A new process owner reconstructs A solely from the serialized selection.
        owner = hosted.build_registered_pandapower_thread_application().capability_context_owner
        assert prepare_and_verify(replace(first, submission=frozen), a) is not prepared_a
    finally:
        pointer.write_bytes(original)
        owner.close()
