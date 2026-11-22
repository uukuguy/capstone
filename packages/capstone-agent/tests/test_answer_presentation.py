import pytest
from capstone_agent.answer_presentation import public_answer


def test_native_answer_recovers_only_one_explicit_body_from_duplicate_markers():
    text = 'Unpublished preamble <capstone-answer><capstone-answer>Saved report.</capstone-answer></capstone-answer>'
    assert public_answer(text, recover_unique=True).startswith('Saved report.\n\n')
    with pytest.raises(ValueError, match='answer_presentation_invalid'):
        public_answer('<capstone-answer>A</capstone-answer><capstone-answer>B</capstone-answer>', recover_unique=True)

def test_explicit_answer_excludes_preamble_without_language_heuristics():
    assert public_answer('Planning text\n// 交付结果\n<capstone-answer>中文正文 with English terms.</capstone-answer>') == '中文正文 with English terms.'

def test_legacy_prose_is_not_guessed_or_deleted():
    assert public_answer('English is useful here.') == 'English is useful here.'

def test_bundle_recovers_unique_json_when_answer_tags_repeat():
    bundle = '{"answer":"线路排序","summary":"三条线路"}'
    assert public_answer('<capstone-answer><capstone-answer>'+bundle+'</capstone-answer></capstone-answer>',
                         answer_format='formal-and-core/1') == bundle

def test_bundle_recovery_does_not_choose_between_two_answers():
    with pytest.raises(ValueError, match='answer_presentation_invalid'):
        public_answer('<capstone-answer>{"answer":"甲"}</capstone-answer>'
                      '<capstone-answer>{"answer":"乙"}</capstone-answer>',
                      answer_format='formal-and-core/1')


def test_bundle_recovers_complete_json_before_native_tool_closing_markers():
    bundle = '{"answer":"线路排序","summary":"三条线路"}'
    text = ('<capstone-answer>' + bundle + '</｜｜DSML｜｜ parameter>\n'
            '</｜｜DSML｜｜ invoke>\n</｜｜DSML｜｜ calls>')
    assert public_answer(text, answer_format='formal-and-core/1') == bundle

    with pytest.raises(ValueError, match='answer_presentation_invalid'):
        public_answer(text + '\n另一个答案', answer_format='formal-and-core/1')

@pytest.mark.parametrize('text', ['<capstone-answer>x', '<capstone-answer></capstone-answer>', '<capstone-answer>x</capstone-answer>extra'])
def test_malformed_boundary_is_rejected(text):
    with pytest.raises(ValueError, match='answer_presentation_invalid'):
        public_answer(text)


def test_split_formal_and_core_keeps_the_complete_formal_answer():
    import json

    text = ('<capstone-answer>完整报告\n第一项和第二项。</capstone-answer>\n\n'
            '<capstone-answer-summary>{"answer":"简写的报告","summary":"两项已核对。"}'
            '</｜｜DSML｜｜ parameter>\n</｜｜DSML｜｜ invoke>\n</｜｜DSML｜｜ calls>')
    assert json.loads(public_answer(text, answer_format='formal-and-core/1')) == {
        'answer': '完整报告\n第一项和第二项。', 'summary': '两项已核对。'}
    recovered = json.loads(public_answer(text + '\n额外正文', answer_format='formal-and-core/1'))
    assert recovered['answer'].startswith('完整报告\n第一项和第二项。')
    assert '格式异常' in recovered['answer']
    assert '额外正文' not in recovered['answer'] and recovered['summary'] is None


def test_invalid_summary_does_not_hide_a_valid_formal_answer():
    import json

    text = '<capstone-answer>{"answer":"计算已完成","summary":42}</capstone-answer>内容额外'
    recovered = json.loads(public_answer(text, answer_format='formal-and-core/1'))
    assert recovered['answer'].startswith('计算已完成')
    assert '格式异常' in recovered['answer']
    assert recovered['summary'] is None


def test_literal_line_breaks_keep_answer_and_summary_separate():
    import json

    text = '<capstone-answer>{"answer":"第一段\n第二段","summary":"摘要"}</capstone-answer>'
    assert json.loads(public_answer(text, answer_format='formal-and-core/1')) == {
        'answer': '第一段\n第二段', 'summary': '摘要'}
