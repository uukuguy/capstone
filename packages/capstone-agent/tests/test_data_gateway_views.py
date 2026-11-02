from capstone_agent.data_gateway_views import GatewayViewBindings


def catalog():
    names = ('brand_new_reader', 'renamed_poll', 'renamed_open')
    return {'revision': 'r', 'tools': {'data_gateway_' + n: {'inputSchema': {'type': 'object'}} for n in names},
            'tool_hashes': {'data_gateway_' + n: 'sha' for n in names}}



def test_renamed_actions_are_exact_and_terminal_jobs_clear_continuation():
    bindings = GatewayViewBindings()
    action = {'tool': 'brand_new_reader', 'arguments': {'view_ref': 'v', 'stream': 'devices'}}
    bindings.observe('selected_by_model', {}, {'structuredContent': {'status': 'ok', 'data': {
        'schema': 'gateway-electrical-view/2', 'state': 'ready', 'view_ref': 'v',
        'streams': {'devices': {'read': action}}}}}, catalog())
    assert bindings.action(action['arguments']) == action
    assert bindings.action({**action['arguments'], 'limit': 1}) is None
    bindings.observe('brand_new_reader', action['arguments'], {'structuredContent': {
        'status': 'ok', 'data': {'records': [], 'complete': True}}}, catalog())
    assert bindings.action(action['arguments']) == action
    poll = {'tool': 'renamed_poll', 'arguments': {'job_ref': 'j'}}
    bindings.observe('start', {}, {'structuredContent': {'status': 'ok', 'data': {
        'state': 'preparing', 'preparation_ref': 'j', 'next_action': poll}}}, catalog())
    assert bindings.action({'job_ref': 'j'}) == poll
    bindings.observe('renamed_poll', {'job_ref': 'j'}, {'structuredContent': {'status': 'ok',
        'data': {'state': 'succeeded', 'job_ref': 'j'}}}, catalog())
    assert bindings.action({'job_ref': 'j'}) is None


def test_discovery_keeps_published_names_and_open_arguments():
    bindings = GatewayViewBindings()
    data = {'scopes': [], 'count': 0, 'electrical_views': {'open_tool': 'renamed_open',
        'source_grid_models': [{'open_arguments': {'model_ref': 'm'}}]}}
    bindings.observe('model_selected_discovery', {}, {'structuredContent': {'status': 'ok', 'data': data}}, catalog())
    assert bindings.discovery() == data
    assert bindings.action({'model_ref': 'm'}) == {'tool': 'renamed_open', 'arguments': {'model_ref': 'm'}}


def test_succeeded_job_keeps_returned_read_action():
    bindings = GatewayViewBindings()
    action = {'tool': 'brand_new_reader', 'arguments': {'view_ref': 'v', 'stream': 'devices'}}
    bindings.observe('renamed_poll', {'job_ref': 'j'}, {'structuredContent': {'status': 'ok',
        'data': {'state': 'succeeded', 'next_action': action}}}, catalog())
    assert bindings.action(action['arguments']) == action


def test_unpublished_and_ambiguous_actions_are_not_selected():
    bindings = GatewayViewBindings()
    response = {'structuredContent': {'status': 'ok', 'data': {}, 'provenance': {
        'agent_guidance': {'next_actions': [
            {'tool': 'brand_new_reader', 'arguments': {}},
            {'tool': 'renamed_open', 'arguments': {}},
            {'tool': 'unpublished', 'arguments': {'x': 1}}]}}}}
    bindings.observe('model_selected', {}, response, catalog())
    assert bindings.action({}) is None
    assert bindings.action({'x': 1}) is None


def test_invalid_optional_action_arguments_do_not_fail_observation():
    bindings = GatewayViewBindings()
    publication = catalog()
    publication['tools']['data_gateway_renamed_poll']['inputSchema'] = {
        'type': 'object', 'required': ['job_ref'], 'properties': {'job_ref': {'type': 'string'}}}
    bindings.observe('selected', {}, {'structuredContent': {'status': 'ok', 'data': {
        'next_action': {'tool': 'renamed_poll', 'arguments': {'job_ref': 1}}}}}, publication)
    assert bindings.action({'job_ref': 1}) is None


def test_failed_observation_removes_old_poll_without_admitting_failed_guidance():
    bindings = GatewayViewBindings()
    poll = {'tool': 'renamed_poll', 'arguments': {'job_ref': 'j'}}
    bindings.observe('start', {}, {'structuredContent': {'status': 'ok', 'data': {
        'next_action': poll}}}, catalog())
    bindings.observe('renamed_poll', poll['arguments'], {'isError': True, 'structuredContent': {
        'status': 'error', 'data': {'next_action': poll}}}, catalog())
    assert bindings.action(poll['arguments']) is None


def test_ambiguous_action_bucket_has_a_fixed_memory_bound():
    bindings = GatewayViewBindings()
    publication = catalog()
    for index in range(100):
        name = f'reader_{index}'
        publication['tools']['data_gateway_' + name] = {'inputSchema': {'type': 'object'}}
        publication['tool_hashes']['data_gateway_' + name] = 'sha'
        bindings.observe('selected', {}, {'structuredContent': {'status': 'ok', 'data': {
            'next_action': {'tool': name, 'arguments': {'view_ref': 'v'}}}}}, publication)
    assert bindings.action({'view_ref': 'v'}) is None
    assert len(bindings._actions[bindings._key({'view_ref': 'v'})]) <= 2


def test_app_pagination_hint_keeps_exact_cursor_and_rejects_ambiguous_calls():
    bindings = GatewayViewBindings()
    arguments = {'view_ref': 'v', 'stream': 'devices', 'cursor': 'signed-cursor'}
    action = {'tool': 'brand_new_reader', 'arguments': arguments}
    bindings.observe('reader', {}, {'structuredContent': {'status': 'ok', 'data': {
        'next_action': action}}}, catalog())
    assert bindings.view_action({**arguments, 'limit': 500}, read=True) == action
    assert bindings.view_action({**arguments, 'cursor': 'other', 'limit': 500}, read=True) is None
    bindings.observe('reader', {}, {'structuredContent': {'status': 'ok', 'data': {
        'next_action': {'tool': 'renamed_open', 'arguments': arguments}}}}, catalog())
    assert bindings.view_action({**arguments, 'limit': 500}, read=True) is None


def test_mirrored_stream_and_guidance_actions_deduplicate_by_invocation():
    bindings = GatewayViewBindings()
    action = {'tool': 'brand_new_reader', 'arguments': {'view_ref': 'v', 'stream': 'devices'}}
    bindings.observe('selected', {}, {'structuredContent': {'status': 'ok', 'data': {
        'state': 'ready', 'streams': {'devices': {'read': action}}},
        'provenance': {'agent_guidance': {'next_actions': [
            {**action, 'purpose': 'read_default_stream'}]}}}}, catalog())
    assert bindings.action(action['arguments']) == action
    assert bindings.view_action({**action['arguments'], 'limit': 500}, read=True) == action


def test_mirrored_poll_next_action_and_guidance_are_one_invocation():
    bindings = GatewayViewBindings()
    action = {'tool': 'renamed_poll', 'arguments': {'job_ref': 'j'}}
    bindings.observe('selected', {}, {'structuredContent': {'status': 'ok', 'data': {
        'state': 'preparing', 'next_action': action},
        'provenance': {'agent_guidance': {'next_actions': [
            {**action, 'purpose': 'suggested_by_result', 'not_before_seconds': 2}]}}}}, catalog())
    assert bindings.action(action['arguments']) == action
