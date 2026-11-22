"""Inspect saved native receipts and recover delivery after a recorded worker exit."""
from hashlib import sha256
import logging
from types import SimpleNamespace

from .native_failure_origin import native_failure_origin


def recover_exited_native_deliveries(service, executor) -> int:
    read_terminal = getattr(executor, 'observe_terminal_task', None)
    if not callable(read_terminal):
        return 0
    from .enterprise_context import TaskContext
    from .harness import AdmittedAttemptAnswer, terminal_payload_for_admission
    from .native_artifact_projection import project_native_artifacts, retain_native_artifact
    from .pi_delegation import PiTaskResult
    from .structural_context import AUTHORITY_REFERENCE_SOURCE, GATEWAY_OPERATION_SOURCE
    from .thread_protocol import AttemptSnapshot

    recovered = 0
    for candidate in service.native_delivery_recovery_candidates():
        binding = candidate['binding']
        attempt_id = candidate['attempt_id']
        task_id = 'pi-' + sha256((attempt_id + '\0conversation').encode()).hexdigest()
        payload, artifacts, outcome = None, [], 'unavailable'
        try:
            if (binding.get('task_id'), binding.get('parent_attempt_id')) != (task_id, attempt_id):
                raise ValueError('native delivery binding differs from the original instruction')
            result = read_terminal(task_id, attempt_id, binding['executor_identity'])
            if result is not None:
                if (not isinstance(result, PiTaskResult)
                        or (result.task_id, result.parent_attempt_id) != (task_id, attempt_id)
                        or result.to_document()['executor_identity'] != binding['executor_identity']):
                    raise ValueError('native receipt identity differs from the original instruction')
                outcome = 'ineligible'
                if result.status in {'failed', 'cancelled'}:
                    code = (result.failure or {}).get('code')
                    if code in {'native_execution_outcome_unknown', 'native_process_cleanup_unconfirmed',
                                'native_result_retention_expired'}:
                        outcome = 'unavailable'
                    else:
                        outcome = 'terminal_observed'
                        payload = {'status': result.status, 'error_code': code}
                if (result.status == 'completed' and result.answer.strip() and result.failure is None
                        and not any(source['kind'] in {AUTHORITY_REFERENCE_SOURCE, GATEWAY_OPERATION_SOURCE}
                                    for source in result.sources)):
                    outcome = 'unavailable'
                    attempt = AttemptSnapshot(candidate['turn_id'], attempt_id, candidate.get('phase', 'interrupted'),
                                              candidate['model_context_id'], candidate['runtime_mode'])
                    context = candidate['task_context_snapshot']
                    original = SimpleNamespace(attempt=attempt, thread_id=candidate['thread_id'],
                        run_id=candidate['run_id'], task_context=None if context is None else TaskContext.from_document(context))
                    projected = project_native_artifacts(original, result)
                    objects = getattr(service, '_material_objects', None)
                    if projected and objects is None:
                        raise OSError('durable artifact storage is unavailable')
                    for artifact in projected:
                        try:
                            retain_native_artifact(objects, executor, artifact)
                        except Exception as error:
                            logging.getLogger(__name__).warning(
                                'Native artifact recovery failed; attempt_id=%s artifact_id=%s exception_type=%s',
                                attempt_id, artifact['artifact_id'], type(error).__name__)
                        else:
                            artifacts.append(artifact)
                    if len(artifacts) == len(projected):
                        answer, summary = result.answer, None
                        if binding['delivery_recovery_format'] == 'formal-and-core/1':
                            from capability_agent.application.answer_format import parse_answer_bundle
                            bundle = parse_answer_bundle(answer, runtime_limits={'answer_summary_chars': 480})
                            answer, summary = bundle.answer, bundle.summary
                        payload = terminal_payload_for_admission(
                            AdmittedAttemptAnswer(answer, 'offline_information', 'general_knowledge'))
                        if summary:
                            payload['answer_core_summary'] = summary
                        outcome = 'recovered'
        except Exception as error:
            logging.getLogger(__name__).warning(
                'Native delivery recovery unavailable attempt_id=%s exception_type=%s origin=%s',
                attempt_id, type(error).__name__, native_failure_origin(error))
        try:
            recovered += service.record_native_delivery_recovery(candidate, outcome, payload, artifacts)
        except Exception as error:
            logging.getLogger(__name__).warning(
                'Native delivery recovery write failed attempt_id=%s exception_type=%s',
                attempt_id, type(error).__name__)
    return recovered


def observe_lost_contact(service, executor) -> int:
    read_terminal = getattr(executor, 'observe_terminal_task', None)
    read_contact = getattr(executor, 'observe_task_contact', None)
    if not callable(read_terminal):
        return 0
    recorded = 0
    for candidate in service.native_recovery_candidates():
        binding = candidate['binding']
        attempt_id = candidate['attempt_id']
        expected_task = 'pi-' + sha256((attempt_id + '\0conversation').encode()).hexdigest()
        if binding.get('task_id') != expected_task or binding.get('parent_attempt_id') != attempt_id:
            continue
        try:
            identity = (expected_task, attempt_id, binding['executor_identity'])
            status = read_contact(*identity) if callable(read_contact) else 'unknown'
            if status not in {'admitted', 'queued', 'running'}:
                terminal = read_terminal(*identity)
                status = 'unknown' if terminal is None else terminal.status
        except Exception as error:
            logging.getLogger(__name__).warning(
                'Native recovery lookup unavailable; attempt_id=%s exception_type=%s origin=%s',
                attempt_id, type(error).__name__, native_failure_origin(error))
            status = 'unknown'
        if status not in {'admitted', 'queued', 'running', 'completed', 'failed', 'cancelled'}:
            status = 'unknown'
        recorded += service.record_native_recovery_observation(candidate, status)
    return recorded
