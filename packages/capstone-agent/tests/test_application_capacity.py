import pytest

from capstone_agent.application_capacity import (
    CapacityExceeded, current_capacity, initialize_capacity, limits, require_capacity,
)


@pytest.fixture(autouse=True)
def reset_capacity():
    initialize_capacity()
    yield
    initialize_capacity()


def test_initialization_changes_already_imported_consumers():
    before = current_capacity()
    selected = initialize_capacity({'artifact_file_bytes': 128 * 1024**2})
    assert limits.artifact_file_bytes == 128 * 1024**2
    assert selected.fingerprint != before.fingerprint
    assert before.values['artifact_file_bytes'] == 64 * 1024**2
    with pytest.raises(TypeError):
        selected.values['artifact_file_bytes'] = 1


def test_mcp_total_call_budget_is_optional_and_positive_budget_is_exact():
    initialize_capacity({'mcp_call_count': 0})
    from capstone_agent.application_capacity import observe_capacity
    assert observe_capacity('mcp_call_count', 1025) is False
    for count in range(1, 1026):
        require_capacity('mcp_call_count', count, 'mcp_call')
    initialize_capacity({'mcp_call_count': 2})
    require_capacity('mcp_call_count', 2, 'mcp_call')
    with pytest.raises(CapacityExceeded) as caught:
        require_capacity('mcp_call_count', 3, 'mcp_call')
    assert caught.value.dimension == 'mcp_call_count'
    assert caught.value.limit == 2


@pytest.mark.parametrize('override', [{'unknown': 1}, {'artifact_count': True},
    {'artifact_count': 0}, {'artifact_count': -1}, {'artifact_count': 1.5}])
def test_rejects_invalid_initialization(override):
    with pytest.raises(ValueError):
        initialize_capacity(override)


def test_environment_and_explicit_initialization_are_merged():
    profile = initialize_capacity({'artifact_count': 1000}, environment={
        'CAPSTONE_CAPACITY_JSON': '{"limits":{"artifact_count":500},"schema":"capstone-capacity-profile/1"}'})
    assert profile.values['artifact_count'] == 1000
    assert profile.to_document()['limits']['upload_file_bytes'] >= 64 * 1024**3


def test_capacity_error_has_safe_actual_and_configured_values():
    initialize_capacity({'artifact_count': 2})
    with pytest.raises(CapacityExceeded) as caught:
        require_capacity('artifact_count', 3, 'persistence')
    assert caught.value.to_document() == {'code': 'capacity_exceeded',
        'dimension': 'artifact_count', 'actual': 3, 'limit': 2,
        'phase': 'persistence', 'unit': 'items', 'retryable': False}
    require_capacity('provider_stream_bytes', 100_000_000)


def test_debug_mode_preserves_soft_recovery_and_hard_limits_and_is_fingerprinted():
    from capstone_agent.application_capacity import observe_capacity
    normal = initialize_capacity({'artifact_count': 2})
    assert observe_capacity('artifact_count', 3, 'publication') is True
    debug = initialize_capacity({'artifact_count': 2}, mode='debug')
    assert debug.mode == 'debug'
    assert debug.fingerprint != normal.fingerprint
    assert debug.to_document()['mode'] == 'debug'
    assert observe_capacity('artifact_count', 3, 'publication') is True
    with pytest.raises(CapacityExceeded) as caught:
        require_capacity('artifact_count', 3, 'publication')
    assert caught.value.to_document()['fatal'] is True
    assert caught.value.to_document()['mode'] == 'debug'


def test_mode_environment_document_and_explicit_precedence():
    profile = initialize_capacity(environment={'CAPSTONE_CAPACITY_MODE': 'debug'})
    assert profile.mode == 'debug'
    assert initialize_capacity(profile.to_document()).mode == 'debug'
    assert initialize_capacity(profile, mode='normal').mode == 'normal'
    with pytest.raises(ValueError, match='mode'):
        initialize_capacity(mode='silent')
