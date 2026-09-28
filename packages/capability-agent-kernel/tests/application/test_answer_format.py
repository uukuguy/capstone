from capability_agent.application.answer_format import AnswerBundle, parse_answer_bundle


def test_parse_answer_bundle_accepts_json_and_preserves_markdown_answer() -> None:
    result = parse_answer_bundle(
        '{"answer":"## 完整回答\\n\\n线路 11 已完成校核。","summary":"已完成线路 11 校核。"}'
    )

    assert result == AnswerBundle(
        answer="## 完整回答\n\n线路 11 已完成校核。",
        summary="已完成线路 11 校核。",
        diagnostic_codes=(),
    )


def test_parse_answer_bundle_accepts_fenced_json() -> None:
    result = parse_answer_bundle(
        '```json\n{"answer":"正式回答。","summary":"过程摘要。"}\n```'
    )

    assert result.answer == "正式回答。"
    assert result.summary == "过程摘要。"
    assert result.diagnostic_codes == ()


def test_parse_answer_bundle_extracts_json_after_provider_preamble() -> None:
    result = parse_answer_bundle(
        "I'll open the analysis guide first."
        '{"answer":"已打开登记网络。","summary":"已完成网络核对。"}'
    )

    assert result.answer == "已打开登记网络。"
    assert result.summary == "已完成网络核对。"
    assert result.diagnostic_codes == ()


def test_parse_answer_bundle_keeps_legacy_text_with_fallback_diagnostic() -> None:
    result = parse_answer_bundle("旧版正式回答。")

    assert result.answer == "旧版正式回答。"
    assert result.summary is None
    assert result.diagnostic_codes == ("answer_bundle_unavailable",)


def test_parse_answer_bundle_rejects_missing_answer_but_does_not_block_text() -> None:
    result = parse_answer_bundle('{"summary":"没有正式回答。"}')

    assert result.answer == '{"summary":"没有正式回答。"}'
    assert result.summary is None
    assert result.diagnostic_codes == ("answer_bundle_invalid",)


def test_parse_answer_bundle_rejects_empty_or_oversized_summary() -> None:
    empty = parse_answer_bundle('{"answer":"正式回答。","summary":"  "}')
    oversized = parse_answer_bundle(
        '{"answer":"正式回答。","summary":"' + ('摘要' * 111) + '"}'
    )

    assert empty.summary is None
    assert empty.diagnostic_codes == ("answer_summary_invalid",)
    assert oversized.summary is None
    assert oversized.diagnostic_codes == ("answer_summary_invalid",)
