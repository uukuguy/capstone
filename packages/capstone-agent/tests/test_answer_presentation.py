import pytest
from capstone_agent.answer_presentation import public_answer

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

@pytest.mark.parametrize('text', ['<capstone-answer>x', '<capstone-answer></capstone-answer>', '<capstone-answer>x</capstone-answer>extra'])
def test_malformed_boundary_is_rejected(text):
    with pytest.raises(ValueError, match='answer_presentation_invalid'):
        public_answer(text)
