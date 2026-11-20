import pytest

from capstone_agent.thread_input import validate_submission


@pytest.mark.parametrize('legacy_value', [True, False])
def test_legacy_research_selection_is_ignored(legacy_value):
    accepted = validate_submission({'text': 'Inspect saved files', 'deep_research': legacy_value},
                                   mode='capstone', objects=[])
    assert accepted == validate_submission({'text': 'Inspect saved files'}, mode='capstone', objects=[])
