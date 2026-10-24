from capstone_agent.progress import project_native_tool_activity


def test_native_activity_bounds_and_redacts_receipt():
    receipt = project_native_tool_activity({
        "args": {"command": "python report.py --api_key=private"},
        "result": {"content": [{"type": "text", "text": "password=private " + "x" * 900}]},
    })
    assert "report.py" in receipt["operation"]
    assert "private" not in str(receipt)
    assert len(receipt["output_excerpt"]) <= 601
    assert set(receipt) == {"operation", "output_excerpt"}


def test_native_activity_omits_unknown_frames_and_binary_content():
    assert project_native_tool_activity({
        "args": {"content": "private file body"},
        "result": {"content": [{"type": "image", "data": "private"}]},
    }) == {}


def test_native_activity_hides_complete_configuration_output():
    result = project_native_tool_activity({"result": {"content": [
        {"type": "text", "text": '{"apiKey": "private-value", "models": ["demo"]}'}
    ]}})
    assert result["output_excerpt"] == "输出包含受保护配置或凭据信息，已隐藏。"
    assert "private-value" not in str(result)
