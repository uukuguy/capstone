import json
from capstone_agent.native_failure_origin import native_failure_origin


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
