import pytest

from capstone_agent.harness_validation import Decision, Rule, RulePipeline, Stage


def test_ordered_rules_continue_after_a_finding():
    seen = []
    pipeline = RulePipeline(Stage.ANSWER_PRESENTATION, (
        Rule('fix', 1, lambda value: Decision.corrected(value.strip(), 'space_removed')),
        Rule('check', 1, lambda value: Decision.rejected(value, 'missing_end')),
        Rule('later', 1, lambda value: Decision.corrected(value + '!', 'suffix')),
    ))
    result = pipeline.run(' answer ', observe=seen.append)
    assert result.status == 'corrected'
    assert result.value == 'answer!'
    assert [(item.rule_id, item.status, item.code) for item in seen] == [
        ('fix', 'corrected', 'space_removed'), ('check', 'finding', 'missing_end'),
        ('later', 'corrected', 'suffix'),
    ]
    assert all(item.stage is Stage.ANSWER_PRESENTATION for item in seen)


def test_pipeline_keeps_success_quiet_and_rejects_duplicate_rule_ids():
    rule = Rule('check', 1, Decision.accepted)
    pipeline = RulePipeline(Stage.ANSWER_ADMISSION, (rule,))
    assert pipeline.run('answer', observe=lambda _: pytest.fail('ordinary acceptance logged')).value == 'answer'
    with pytest.raises(ValueError, match='Duplicate'):
        RulePipeline(Stage.ANSWER_ADMISSION, (rule, rule))


def test_library_rules_can_report_and_fail_without_stopping_following_rules():
    from capstone_agent.harness_validation import load_rule_bundle

    def crashed(value):
        raise RuntimeError("private detail")

    document = b'''{"schema":"capstone-harness-rules/1","version":3,"rules":[
      {"id":"missing_item","version":2,"stage":"answer_presentation","target":"answer.text","handler":"find","action":"report"},
      {"id":"crashes","version":1,"stage":"answer_presentation","target":"answer.text","handler":"crash","action":"correct"},
      {"id":"repair","version":1,"stage":"answer_presentation","target":"answer.text","handler":"fix","action":"correct"}
    ]}'''
    bundle = load_rule_bundle(document, {
        'find': lambda value: Decision.rejected(value, 'missing_item'),
        'crash': crashed,
        'fix': lambda value: Decision.corrected(value + '!', 'repaired'),
    })
    observations = []
    result = bundle.pipeline().run('answer', observe=observations.append)
    assert result.value == 'answer!'
    assert [item.status for item in observations] == ['finding', 'rule_error', 'corrected']
    assert all(item.to_payload()['rule_bundle_version'] == 3 for item in observations)
    assert all(item.to_payload()['target'] == 'answer.text' for item in observations)
    assert all('private detail' not in str(item.to_payload()) for item in observations)
    with pytest.raises(ValueError, match='Unknown'):
        load_rule_bundle(document, {})


def test_result_table_findings_are_scoped_and_leave_independent_tables_usable():
    from capstone_agent.result_table_checks import result_table_rule_bundle

    valid = {'rows': [1], 'columns': [{'unit': 'p.u.'}]}
    inconsistent = {'rows': [1, 2], 'columns': [{'unit': ' '}], 'pagination': {'total_rows': 1}}
    pipeline = result_table_rule_bundle().pipeline()
    seen = []
    assert pipeline.run(inconsistent, observe=seen.append).value is inconsistent
    assert pipeline.run(valid, observe=seen.append).value is valid
    assert [item.code for item in seen] == ['table_row_count_exceeds_declared_coverage', 'table_unit_label_blank']
    assert all(item.status == 'finding' and item.target == 'result.table' for item in seen)
