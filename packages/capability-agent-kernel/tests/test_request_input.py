"""Applications select schema identities; canonical content checks stay shared."""
from copy import deepcopy

import pytest

from capability_agent.trajectory.request_input import (
    CanonicalRequestValidationError,
    canonical_request_preview,
    semantic_request_sha256,
    validate_canonical_model_request_document,
)


@pytest.fixture(params=[{}, {'schema_version': 'grid-model-request-input/2.0'}])
def selected_request(request):
    options = request.param
    semantic = {
        'model': {'provider': 'fixture', 'api': 'fixture', 'id': 'fixture'},
        'context': {'system_prompt': None, 'messages': [], 'tools': []},
        'options': {},
    }
    document = {
        'schema_version': options.get('schema_version', 'capstone-model-request-input/2.0'),
        'request_id': 'request-1', 'turn_id': 'turn-1', 'request_index': 1,
        'captured_at': '2026-11-14T00:00:00Z', 'source_event_sequences': [1],
        'context_revision': 0, 'context_state_hash': 'a' * 64,
        'runtime': {'pi_coding_agent_version': 'fixture', 'pi_ai_version': 'fixture',
                    'pi_source_commit': 'b' * 40, 'pi_patch_set_sha256': 'c' * 64},
        'semantic_request': semantic, 'semantic_request_sha256': semantic_request_sha256(semantic),
    }
    return document, options


def test_selected_schema_validates_and_previews_without_changing_input(selected_request):
    document, options = selected_request
    original = deepcopy(document)
    result = validate_canonical_model_request_document(document, **options)
    assert result.semantic_digest_verified
    preview = canonical_request_preview(document, **options)
    assert preview == {key: value for key, value in document.items() if key != 'schema_version'}
    assert document == original


def test_schema_identity_must_match_the_application_selection(selected_request):
    document, options = selected_request
    document['schema_version'] = (
        'capstone-model-request-input/2.0' if options else 'grid-model-request-input/2.0'
    )
    for validate in (validate_canonical_model_request_document, canonical_request_preview):
        with pytest.raises(CanonicalRequestValidationError, match='schema_version'):
            validate(document, **options)


@pytest.mark.parametrize('invalid', ['digest', 'unknown_field'])
def test_schema_selection_does_not_bypass_content_validation(selected_request, invalid):
    document, options = selected_request
    if invalid == 'digest':
        document['semantic_request_sha256'] = '0' * 64
    else:
        document['private_payload'] = 'unadmitted'
    for validate in (validate_canonical_model_request_document, canonical_request_preview):
        with pytest.raises(CanonicalRequestValidationError):
            validate(document, **options)
