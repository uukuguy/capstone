from capstone_agent.progress import project_native_tool_activity


def test_native_activity_bounds_and_redacts_receipt():
    receipt = project_native_tool_activity({
        "args": {"command": "python report.py --api_key=private"},
        "result": {"content": [{"type": "text", "text": "password=private " + "x" * 900}]},
    })
    assert "report.py" in receipt["operation"]
    assert "private" not in str(receipt)
    assert len(receipt["output_excerpt"]) <= 601
    assert set(receipt) == {"operation", "input_excerpt", "output_excerpt"}


def test_native_activity_omits_unknown_frames_and_binary_content():
    assert project_native_tool_activity({
        "args": {"content": "private file body"},
        "result": {"content": [{"type": "image", "data": "private"}]},
    }) == {"input_excerpt": '{"content":"[OMITTED BODY]"}'}


def test_native_activity_keeps_exact_selection_arguments_without_credentials():
    import json
    receipt = project_native_tool_activity({'args': {
        'names': ['remote_one', 'unknown_two'], 'query': 'substation',
        'nested': {'Authorization': 'Bearer private', 'apiKey': 'private'},
        'content': 'private body',
    }})
    args = json.loads(receipt['input_excerpt'])
    assert args['names'] == ['remote_one', 'unknown_two']
    assert args['query'] == 'substation'
    assert 'private' not in receipt['input_excerpt']


def test_native_activity_marks_bounded_input_and_preserves_small_reference_values():
    receipt = project_native_tool_activity({'args': {'view_ref': 'view:abc', 'items': ['x' * 1000] * 200}})
    assert len(receipt['input_excerpt']) <= 4000
    assert 'view:abc' in receipt['input_excerpt']
    assert '[TRUNCATED]' in receipt['input_excerpt']


def test_native_activity_hides_complete_configuration_output():
    result = project_native_tool_activity({"result": {"content": [
        {"type": "text", "text": '{"apiKey": "private-value", "models": ["demo"]}'}
    ]}})
    assert result["output_excerpt"] == "输出包含受保护配置或凭据信息，已隐藏。"
    assert "private-value" not in str(result)
