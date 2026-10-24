from __future__ import annotations

import pytest


@pytest.mark.parametrize('reason', [
    'TypeError: keys must be str, int, float, bool or None, not tuple\nCommand exited with code 1',
    'Requested operation could not read the selected file. Exit status: 2',
])
def test_failed_native_activity_keeps_long_output_tail_and_operation(reason):
    from capstone_agent.progress import project_native_tool_activity
    text = 'Report table columns\n' + 'ordinary data row\n' * 1000 + reason
    event = {'type': 'tool_execution_end', 'isError': True,
        'args': {'command': 'python work/analyze.py'},
        'result': {'content': [{'type': 'text', 'text': text}]}}
    activity = project_native_tool_activity(event)
    assert reason.replace('\n', ' ') in activity['output_excerpt']
    assert activity['output_excerpt'].startswith('Report table columns')
    assert activity['operation'] == 'python work/analyze.py'
    assert len(activity['output_excerpt']) <= 600
    assert event['result']['content'][0]['text'] == text, 'model result must not change'


def test_short_failed_native_activity_is_preserved_without_fabricated_exit_status():
    from capstone_agent.progress import project_native_tool_activity
    activity = project_native_tool_activity({'isError': True,
        'result': {'content': [{'type': 'text', 'text': 'Cannot read the selected file.'}]}})
    assert activity['output_excerpt'] == 'Cannot read the selected file.'


def test_successful_native_activity_keeps_existing_head_excerpt_despite_error_words():
    from capstone_agent.progress import project_native_tool_activity
    activity = project_native_tool_activity({'isError': False,
        'result': {'content': [{'type': 'text', 'text': 'ordinary row ' * 1000 + 'Traceback example only'}]}})
    assert activity['output_excerpt'].startswith('ordinary row ')
    assert 'Traceback' not in activity['output_excerpt']
    assert activity['output_excerpt'].endswith('…')


@pytest.mark.parametrize('secret', ['api_key=private-value', 'Authorization: Bearer private-value', 'password="private-value"'])
def test_failed_native_activity_checks_secrets_before_selecting_tail(secret):
    from capstone_agent.progress import project_native_tool_activity
    activity = project_native_tool_activity({'isError': True,
        'args': {'command': 'python analyze.py --api_key=operation-private'},
        'result': {'content': [{'type': 'text', 'text': 'row ' * 1000 + secret + '\nFailure at exit 1'}]}})
    assert activity['output_excerpt'] == '输出包含受保护配置或凭据信息，已隐藏。'
    assert 'private' not in str(activity)


def test_tool_failure_summary_uses_only_structured_field_and_parameter_names():
    from capstone_agent.progress import project_tool_failure
    field = project_tool_failure({'code': 'result_field_unavailable', 'message': 'Query rejected',
        'details': {'fields': ['bus'], 'allowed_fields': ['index', 'vm_pu']}})
    assert field['summary'] == '字段不可用：bus；可用字段：index、vm_pu'
    gap = project_tool_failure({'code': 'analysis_prerequisite_missing', 'message': 'No result produced',
        'details': {'parameter_gaps': [{'element_kind': 'source', 'index': 2, 'field': 'capacity'},
            {'field': 'api_key=private-value'}], 'provider': {'secret': 'private-value'}}})
    assert gap['summary'] == '参数缺失或无效：source[2].capacity'
    assert 'private-value' not in str(gap)

from capstone_agent.progress import render_progress, summarize_answer


def test_progress_renders_tools_and_redacts_credentials() -> None:
    message = render_progress({
        "type": "tool_execution_start", "toolName": "grid_powerflow_run",
        "args": {"network": "case39", "api_key": "secret-value"},
    })

    assert "grid_powerflow_run" in message
    assert "case39" in message
    assert "secret-value" not in message
    assert "bearer-secret" not in render_progress({
        "type": "tool_execution_end", "toolName": "grid_powerflow_run",
        "result": {"detail": "Authorization: Bearer bearer-secret"},
    })


def test_progress_renders_report_checkpoint() -> None:
    message = render_progress({
        "type": "application_report_checkpoint",
        "completed_questions": 2, "total_questions": 3,
        "report_path": "runs/run-1/output/report.md",
    })

    assert "已完成 2 题" in message
    assert "runs/run-1/output/report.md" in message


def test_progress_summarizes_semantic_tool_events_without_hashes_or_rows() -> None:
    digest = "a" * 64
    started = render_progress({
        "type": "tool_execution_start", "toolName": "grid_model_dataset_query",
        "args": {"context_ref": f"context:sha256:{digest}", "dataset": "network.bus",
                 "filters": [{"field": "in_service", "operator": "eq", "value": True}]},
    })
    completed = render_progress({
        "type": "tool_result", "toolName": "grid_model_dataset_query", "ok": True,
        "result": {"dataset_ref": f"dataset:sha256:{digest}", "dataset": "network.bus",
                   "row_count": 39, "returned_row_count": 39,
                   "rows": [{"index": i, "in_service": True} for i in range(39)]},
    })
    assert "grid_model_dataset_query" in started
    assert "network.bus" in started
    assert "工具完成" in completed
    assert "39" in completed
    assert digest not in started + completed
    assert '"rows"' not in completed
    assert len(started) < 150 and len(completed) < 150


def test_progress_reports_prompt_and_assistant_message() -> None:
    assert render_progress({"type": "response", "command": "prompt", "success": True}) == "模型请求已接收"
    assert render_progress({"type": "assistant_message", "text": "正在核对网络数据"}) == "正在整理本步回答"


def test_summarize_answer_hides_model_process_narration() -> None:
    answer = "I'll inspect the model first. Now I will validate it.\n\n已完成：模型包含 6 个母线。"
    assert summarize_answer(answer, has_references=True) == "已完成：模型包含 6 个母线。"


def test_summarize_answer_always_keeps_process_output_compact() -> None:
    answer = "基于当前潮流结果，负载率最高的三条线路如下：线路 21、线路 11、线路 26。"
    assert summarize_answer(answer, has_references=True) == answer


def test_summarize_answer_uses_lead_sentence_before_markdown_table() -> None:
    answer = "基于当前潮流结果，负载率最高的三条线路如下： | 排名 | 线路 | 负载率 |"
    assert summarize_answer(answer, has_references=True) == "基于当前潮流结果，负载率最高的三条线路如下："


def test_summarize_answer_drops_chinese_planning_prefix_before_heading() -> None:
    answer = "我先查阅已发布指南并打开注册网络。## 网络核对结果\n\n已完成核查。"
    assert summarize_answer(answer, has_references=True) == "网络核对结果 已完成核查。"


def test_progress_summarizes_small_named_counts() -> None:
    message = render_progress({
        "type": "tool_result", "toolName": "grid_context_open", "ok": True,
        "result": {"model": "ieee39", "counts": {"buses": 39, "lines": 35, "transformers": 11}},
    })
    assert "ieee39" in message
    assert "buses=39" in message
    assert "lines=35" in message
