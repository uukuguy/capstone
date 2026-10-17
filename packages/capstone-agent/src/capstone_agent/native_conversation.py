"""Application-owned native conversation binding over the existing Pi host."""
import json
from typing import cast
from collections.abc import Mapping

from .general_executor_composition import _resource_profiles


def executor_binding(executor) -> dict:
    from .delegated_runtime import json_document
    capability = cast(dict, json_document(executor.capability))
    identity = cast(dict, json_document(executor.identity))
    if (not identity or capability.get('capability_id') != 'general-pi'
            or capability.get('enabled') is not True or capability.get('available') is not True
            or 'answer' not in capability.get('operations', ())):
        raise ValueError('native conversation executor is unavailable')
    if 'capstone-native-context/1' not in capability.get('native_context_schemas', ()):
        raise ValueError('native conversation context contract is unavailable')
    _resource_profiles(capability.get('resource_profiles', {}))
    if 'delegated_pi' not in capability.get('resource_profiles', {}):
        raise ValueError('native conversation resource profile is unavailable')
    from .enterprise_application import resolve_enterprise_research_profile
    from .native_pack_preparation import PiNativeBindingPreparer
    from capability_agent.domain.profile import NativeDomainRuntimeProfile
    from pathlib import Path
    from types import SimpleNamespace
    profile = resolve_enterprise_research_profile()
    binding = profile.domains[0]
    if not isinstance(binding.profile, NativeDomainRuntimeProfile):
        raise ValueError('native application selected an incompatible binding')
    class NativeCredentials:
        scope_id = 'isolated'
        credentials: Mapping[str, str] = {}
    prepared = PiNativeBindingPreparer(executor).prepare(binding=binding, profile=binding.profile,
        workspace=Path('.'), credentials=NativeCredentials())
    if prepared.receipt.resource_revision != capability['resource_profiles']['delegated_pi']['revision']:
        raise ValueError('native resource preparation identity changed')
    prepared.close()
    # Optional retrieval is not an application grant merely because the host
    # supports it. The base conversation has no external lookup permission.
    capability['operations'] = [item for item in capability['operations'] if item in {'answer', 'rewrite'}]
    return {'schema': 'capstone-native-conversation/1',
            'application_profile': {'profile_id': profile.manifest.application_id,
                                    'profile_version': profile.manifest.version},
            'binding_id': binding.binding_id, 'identity': identity, 'capability': capability}


def validate_binding(value: object) -> dict:
    if (not isinstance(value, Mapping) or set(value) != {
            'schema', 'application_profile', 'binding_id', 'identity', 'capability'}
            or value['schema'] != 'capstone-native-conversation/1'
            or value['application_profile'] != {'profile_id': 'enterprise-research', 'profile_version': '1.0.0'}
            or value['binding_id'] != 'native-conversation'):
        raise ValueError('native conversation binding is invalid')
    from types import SimpleNamespace
    checked = executor_binding(SimpleNamespace(identity=value['identity'], capability=value['capability']))
    if checked != value:
        raise ValueError('native conversation binding is inconsistent')
    return json.loads(json.dumps(checked))


class NativeResearchRuntime:
    """Bind the existing ordinary runtime to the same durable Work research."""
    def __init__(self, runtime, claim, root):
        from .attempt_research import AttemptResearch
        self._runtime, self._claim = runtime, claim
        self._completed = False
        self._research = AttemptResearch(root, thread_id=claim.thread_id, run_id=claim.run_id,
            attempt_id=claim.attempt.attempt_id, task_context=claim.task_context,
            is_active=lambda: False, admit_reference=lambda _: False)

    def __getattr__(self, name):
        return getattr(self._runtime, name)

    def bind_attempt_guard(self, check, terminal_phase=None):
        self._check = check
        self._research.bind_active_check(check, terminal_phase)

    def start(self):
        return self._runtime.start()

    def prompt(self, question, *, on_event, correlation_id=None, on_heartbeat=None):
        if not self._check():
            raise InterruptedError('native conversation cancelled')
        answer = self._runtime.prompt(question, correlation_id=correlation_id,
                                      on_event=on_event, on_heartbeat=on_heartbeat)
        if not self._check():
            raise InterruptedError('native conversation cancelled')
        state = self._research.controller.read()
        notes = [] if state is None else [note.model_dump(mode='json') for note in state.notes][-63:]
        from capability_agent.application.research_models import ResearchNote, ResearchState
        note_limit = ResearchNote.model_json_schema()['properties']['text']['maxLength']
        note_prefix = 'Assistant reply excerpt (general knowledge; full reply is in the Attempt record):\n'
        notes.append({'note_id': self._claim.attempt.attempt_id,
            'text': note_prefix + answer[:note_limit - len(note_prefix)],
            'refs': []})
        goal = question if state is None else state.goal
        goal_limit = ResearchState.model_json_schema()['properties']['goal']['maxLength']
        if len(goal) > goal_limit:
            goal_prefix = 'Task request excerpt (full request is in the Attempt record):\n'
            goal = goal_prefix + goal[:goal_limit - len(goal_prefix)]
        self._research.controller.update({'request_id': self._claim.attempt.attempt_id,
            'expected_revision': 0 if state is None else state.revision,
            'changes': {'goal': goal, 'notes': notes}})
        projection = self._research.current_projection()
        on_event({'event_type': 'research_state_updated', 'runtime_mode': self._runtime.runtime_mode,
                  'visibility': 'public', 'payload': projection})
        self._completed = True
        return answer

    def stop(self):
        try:
            self._runtime.stop()
        finally:
            self._research.close(failed=not self._completed)
