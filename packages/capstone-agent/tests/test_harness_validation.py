import pytest

from capstone_agent.harness_validation import Decision, Rule, RulePipeline, Stage


def test_ordered_rules_pass_corrected_value_and_stop_on_rejection():
    seen = []
    pipeline = RulePipeline(Stage.ANSWER_PRESENTATION, (
        Rule('fix', 1, lambda value: Decision.corrected(value.strip(), 'space_removed')),
        Rule('check', 1, lambda value: Decision.rejected(value, 'missing_end')),
        Rule('later', 1, lambda value: pytest.fail('rejected value reached a later rule')),
    ))
    result = pipeline.run(' answer ', observe=seen.append)
    assert result.status == 'rejected'
    assert result.value == 'answer'
    assert [(item.rule_id, item.status, item.code) for item in seen] == [
        ('fix', 'corrected', 'space_removed'), ('check', 'rejected', 'missing_end'),
    ]
    assert all(item.stage is Stage.ANSWER_PRESENTATION for item in seen)


def test_pipeline_keeps_success_quiet_and_rejects_duplicate_rule_ids():
    rule = Rule('check', 1, Decision.accepted)
    pipeline = RulePipeline(Stage.ANSWER_ADMISSION, (rule,))
    assert pipeline.run('answer', observe=lambda _: pytest.fail('ordinary acceptance logged')).value == 'answer'
    with pytest.raises(ValueError, match='Duplicate'):
        RulePipeline(Stage.ANSWER_ADMISSION, (rule, rule))
