from copy import deepcopy

import pytest

from capstone_agent.session_skill_preferences import revise_preferences, freeze_preferences


def catalog(version='v1', ready=True):
    return {'delegated_pi': {'revision': 'catalog-current', 'resources': [
        {'id': 'method', 'kind': 'skill', 'version': version, 'ready': ready, 'loaded_identity': 'a' * 64}]}}


CHOICE = {'id': 'method', 'version': 'v1', 'role': 'delegated_pi'}
PINNED = {**CHOICE, 'loaded_identity': 'a' * 64, 'catalog_revision': 'catalog-current'}


def test_revision_conflict_does_not_replace_session_choices():
    settings = revise_preferences(None, expected_revision=0, skills=[CHOICE], profiles=catalog(), mode='capstone')
    with pytest.raises(ValueError, match='skill_preferences_conflict'):
        revise_preferences(settings, expected_revision=0, skills=[], profiles=catalog(), mode='capstone')
    assert settings == {'revision': 1, 'skills': [PINNED]}


def test_frozen_instruction_survives_disable_and_catalog_change():
    settings = revise_preferences(None, expected_revision=0, skills=[CHOICE], profiles=catalog(), mode='capstone')
    frozen = freeze_preferences(settings, profiles=catalog(), mode='capstone', excluded=[])
    disabled = revise_preferences(settings, expected_revision=1, skills=[], profiles=catalog(), mode='capstone')
    assert disabled == {'revision': 2, 'skills': []}
    assert frozen == {'revision': 1, 'skills': [PINNED], 'excluded': []}
    assert settings['skills'] == [PINNED]
    with pytest.raises(ValueError, match='session_skill_unavailable'):
        freeze_preferences(settings, profiles=catalog('v2'), mode='capstone', excluded=[])


def test_instruction_exclusion_is_local_and_cannot_name_unknown_preferences():
    settings = {'revision': 1, 'skills': [deepcopy(PINNED)]}
    assert freeze_preferences(settings, profiles=catalog(), mode='capstone', excluded=['method'])['skills'] == []
    assert len(freeze_preferences(settings, profiles=catalog(), mode='capstone', excluded=[])['skills']) == 1
    with pytest.raises(ValueError, match='skill_exclusion_invalid'):
        freeze_preferences(settings, profiles=catalog(), mode='capstone', excluded=['other'])


@pytest.mark.parametrize('skills', [[CHOICE, CHOICE], [{**CHOICE, 'role': 'harness_engine'}],
                                   [{**CHOICE, 'endpoint': 'forged'}]])
def test_preferences_cannot_expand_native_roles_or_accept_private_fields(skills):
    with pytest.raises(ValueError):
        revise_preferences(None, expected_revision=0, skills=skills, profiles=catalog(), mode='capstone')


def test_session_command_is_durable_idempotent_and_freezes_each_instruction():
    from test_thread_input import idle_service, command
    from capstone_agent.thread_input_catalog import input_catalog_document
    from capstone_agent.thread_protocol import ThreadSnapshot
    service = idle_service()
    service.set_input_catalog_provider(lambda snapshot: input_catalog_document(snapshot, catalog(), []))
    change = {'schema': 'capstone-command/2', 'thread_id': 'thr_intent',
              'command_id': 'cmd_skills', 'idempotency_key': 'idem_skills',
              'kind': 'set_session_skills',
              'target': {'kind': 'session_skills', 'id': 'thr_intent', 'expected_revision': 0},
              'payload': {'skills': [CHOICE]}}
    assert service.submit_command(change).status == 'accepted'
    assert service.submit_command(change).status == 'accepted'
    restored = ThreadSnapshot.from_document(service.snapshot('thr_intent').to_document())
    assert restored.session_skills == {'revision': 1, 'skills': [PINNED]}
    assert service.submit_command(command(service, input={'kind': 'text', 'text': 'Use this method'})).status == 'accepted'
    attempt = service.claim_attempt('worker_test', 30)
    assert attempt.submission['session_skills']['skills'][0]['id'] == 'method'
    change.update(command_id='cmd_disable', idempotency_key='idem_disable', payload={'skills': []},
                  target={**change['target'], 'expected_revision': 1})
    assert service.submit_command(change).status == 'accepted'
    assert attempt.submission['session_skills']['revision'] == 1
    assert service.snapshot('thr_intent').session_skills['revision'] == 2


def test_method_guidance_is_optional_and_contains_no_prior_goal_or_evidence():
    from capstone_agent.session_skill_preferences import method_guidance
    frozen = freeze_preferences({'revision': 1, 'skills': [PINNED]}, profiles=catalog(), mode='capstone', excluded=[])
    guidance = method_guidance({'session_skills': frozen})
    assert 'method' in guidance
    assert 'not mandatory' in guidance
    assert 'method' in method_guidance({'session_skills': {'revision': 2, 'skills': [], 'excluded': ['method']}})


def test_native_executor_receives_frozen_preference_without_skill_invocation():
    from dataclasses import replace
    from types import SimpleNamespace
    from test_delegated_runtime import Executor, run, factory
    from test_intent_runtime import claim
    service, current = claim()
    context = current.professional_context
    current = replace(current, attempt=replace(current.attempt, runtime_mode='pi_reference'),
        submission={'input': {'kind': 'text', 'text': current.instruction}, 'objects': [
                    {'object_id': context.id, 'model_id': context.model_id,
                     'model_revision': context.model_revision, 'implementation_family': context.implementation_family}],
                    'context_selection': {'include_refs': [], 'exclude_refs': []},
                    'session_skills': {'revision': 3, 'skills': [{**PINNED, 'role': 'direct_pi'}], 'excluded': []}})
    executor = Executor()
    result = run(service, current, factory(executor, SimpleNamespace(identity=None)))
    assert result.status == 'completed', result
    sent = executor.requests[0].to_document()
    assert 'Session method preferences' in sent['instruction']
    assert sent['input']['kind'] == 'text'
    assert sent['input']['text'] == sent['instruction']


def test_postgres_preferences_restore_after_new_service(postgres_thread_service):
    from test_thread_postgres import _snapshot
    from capstone_agent.thread_service import PostgresThreadService
    from capstone_agent.thread_input_catalog import input_catalog_document
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))
    service.set_input_catalog_provider(lambda snapshot: input_catalog_document(snapshot, catalog(), []))
    command = {'schema': 'capstone-command/2', 'thread_id': thread_id,
        'command_id': 'cmd_skills', 'idempotency_key': 'idem_skills', 'kind': 'set_session_skills',
        'target': {'kind': 'session_skills', 'id': thread_id, 'expected_revision': 0},
        'payload': {'skills': [CHOICE]}}
    assert service.submit_command(command).status == 'accepted'
    restored = PostgresThreadService(service.dsn).snapshot(thread_id)
    assert restored.session_skills == {'revision': 1, 'skills': [PINNED]}
    assert restored.current_attempt is None


from test_thread_postgres import postgres_thread_service
