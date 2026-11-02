import json
from capstone_agent.native_failure_origin import native_failure_origin, checked_failure_origin
import pytest


@pytest.mark.parametrize('value', [None, [{'module': '/private/secret', 'function': 'read', 'line': 1}],
    [{'module': 'capstone_agent.reader', 'function': 'read', 'line': True}],
    [{'module': 'capstone_agent.reader', 'function': 'read', 'line': 1, 'error': 'SECRET'}]])
def test_public_failure_origin_rejects_untrusted_fields(value):
    assert checked_failure_origin(value) == []


def test_origin_retains_only_trusted_frame_coordinates_not_failure_text_or_locals():
    from capstone_agent.native_task_context import checked_native_context
    secret = 'PRIVATE_PROMPT_OR_CREDENTIAL'
    try:
        checked_native_context({'untrusted': secret})
    except ValueError as error:
        origin = native_failure_origin(error)
    assert origin
    assert origin[-1]['module'] == 'capstone_agent.native_task_context'
    assert origin[-1]['function'] == 'checked_native_context'
    assert set(origin[-1]) == {'module', 'function', 'line'}
    assert secret not in json.dumps(origin)


def test_untrusted_frames_and_missing_traceback_are_not_recorded():
    assert native_failure_origin(ValueError('private')) == []
    try:
        raise ValueError('private')
    except ValueError as error:
        assert native_failure_origin(error) == []


def test_wrapped_failure_keeps_original_trusted_origin_without_error_text():
    from capstone_agent.native_task_context import checked_native_context
    try:
        try:
            checked_native_context({'untrusted': 'PRIVATE'})
        except ValueError as cause:
            raise RuntimeError('wrapper PRIVATE') from cause
    except RuntimeError as error:
        origin = native_failure_origin(error)
    assert origin[-1]['function'] == 'checked_native_context'
    assert checked_failure_origin(origin) == origin
    assert 'PRIVATE' not in json.dumps(origin)
