from copy import deepcopy
from types import SimpleNamespace

import pytest

from capstone_agent.session_skill_preferences import revise_preferences, freeze_preferences, method_guidance


CHOICE = {'id': 'method', 'version': '1.0', 'role': 'direct_pi'}


def profile():
    return {'direct_pi': {'revision': 'catalog-A', 'resources': [
        {'id': 'method', 'version': '1.0', 'kind': 'skill', 'ready': True,
         'native_name': 'sample', 'loaded_identity': 'a' * 64}]}}


def test_choice_pins_content_and_rejects_same_version_replacement():
    profiles = profile()
    settings = revise_preferences(None, expected_revision=0, skills=[CHOICE], profiles=profiles, mode='pi_reference')
    assert settings['skills'][0]['loaded_identity'] == 'a' * 64
    profiles['direct_pi']['revision'] = 'catalog-B'
    profiles['direct_pi']['resources'][0]['loaded_identity'] = 'b' * 64
    with pytest.raises(ValueError, match='session_skill_content_changed'):
        freeze_preferences(settings, profiles=profiles, mode='pi_reference', excluded=[])


def test_legacy_preference_requires_explicit_reselection_but_can_be_excluded():
    settings = {'revision': 1, 'skills': [CHOICE]}
    with pytest.raises(ValueError, match='session_skill_reselect_required'):
        freeze_preferences(settings, profiles=profile(), mode='pi_reference', excluded=[])
    frozen = freeze_preferences(settings, profiles=profile(), mode='pi_reference', excluded=['method'])
    assert 'method' in method_guidance({'session_skills': frozen})


def test_native_resource_loader_removes_excluded_method(tmp_path):
    from test_runtime_resources import config
    from capstone_agent.native_resources import NativeResourceStore
    root = config(tmp_path)
    store = NativeResourceStore(root, tmp_path / 'profiles')
    from hashlib import sha256
    accepted = store.confirm_loaded('direct_pi', {'tools': ['read'], 'skills': [
        {'name': 'sample', 'sha256': sha256((root / 'native/skill/SKILL.md').read_bytes()).hexdigest()}]})
    method = next(item for item in accepted.resources if item.kind == 'skill')
    scope = {'schema': 'capstone-session-skill-scope/1', 'revision': 1, 'skills': [], 'excluded': [method.resource_id]}
    request = SimpleNamespace(instruction='Explain', task_id='task', parent_attempt_id='attempt',
        to_document=lambda: {'skill_scope': scope})
    baseline = SimpleNamespace(instruction='Explain', task_id='task', parent_attempt_id='attempt', to_document=lambda: {})
    assert method.native_name in store.task_config('direct_pi', accepted.revision, workspace=tmp_path / 'task', request=baseline)['allowedSkills']
    values = store.task_config('direct_pi', accepted.revision, workspace=tmp_path / 'task', request=request)
    assert method.native_name not in values['allowedSkills']


def test_native_loader_checks_frozen_content_identity(tmp_path):
    from test_runtime_resources import config
    from capstone_agent.native_resources import NativeResourceStore
    store = NativeResourceStore(config(tmp_path), tmp_path / 'profiles')
    accepted = store.profiles['direct_pi']
    method = next(item for item in accepted.resources if item.kind == 'skill')
    scope = {'schema': 'capstone-session-skill-scope/1', 'revision': 1, 'skills': [
        {'id': method.resource_id, 'version': method.version, 'role': 'direct_pi',
         'loaded_identity': 'wrong-content', 'native_name': method.native_name,
         'catalog_revision': accepted.revision}], 'excluded': []}
    request = SimpleNamespace(instruction='Explain', task_id='task', parent_attempt_id='attempt',
        to_document=lambda: {'skill_scope': scope})
    with pytest.raises(ValueError, match='session_skill_content_changed'):
        store.task_config('direct_pi', accepted.revision, workspace=tmp_path / 'task', request=request)


def test_exclusion_crosses_native_task_transport_without_prompt_dependence():
    from dataclasses import replace
    from test_delegated_runtime import Executor, run, factory
    from test_intent_runtime import claim
    from capstone_agent.pi_delegation import PiTaskRequest
    service, current = claim()
    context = current.professional_context
    current = replace(current, attempt=replace(current.attempt, runtime_mode='pi_reference'),
        submission={'input': {'kind': 'text', 'text': current.instruction},
            'objects': [{'object_id': context.id, 'model_id': context.model_id,
                        'model_revision': context.model_revision, 'implementation_family': context.implementation_family}],
            'context_selection': {'include_refs': [], 'exclude_refs': []},
            'session_skills': {'revision': 7, 'skills': [], 'excluded': ['method']}})
    executor = Executor()
    result = run(service, current, factory(executor, SimpleNamespace(identity=None)))
    assert result.status == 'completed', result
    sent = executor.requests[0].to_document()
    assert sent['skill_scope']['excluded'] == ['method']
    assert PiTaskRequest.from_document(sent).to_document()['skill_scope'] == sent['skill_scope']


def test_unrelated_catalog_revision_does_not_replace_pinned_content():
    profiles = profile()
    settings = revise_preferences(None, expected_revision=0, skills=[CHOICE], profiles=profiles, mode='pi_reference')
    profiles['direct_pi']['revision'] = 'unrelated-update'
    frozen = freeze_preferences(settings, profiles=profiles, mode='pi_reference', excluded=[])
    assert frozen['skills'][0]['loaded_identity'] == settings['skills'][0]['loaded_identity']
