import pytest

from capstone_agent.harness_validation import Decision, Rule, RulePipeline, Stage


def test_archived_validation_replays_exact_input_and_compares_candidate():
    from capstone_agent.answer_correction import presentation_rule_bundle
    from capstone_agent.artifacts import MemoryObjectStore
    from capstone_agent.harness_validation import archive_rule_input, load_rule_bundle, replay_rule_input

    objects = MemoryObjectStore()
    bundle = presentation_rule_bundle()
    original = 'Original answer'
    ref = archive_rule_input(objects, 'thread', 'attempt', bundle, original, answer_limit=30)
    replay = replay_rule_input(objects, 'thread', 'attempt', ref, bundle)
    assert replay.value == original
    candidate = load_rule_bundle(bundle.source.replace(b'"version": 1,', b'"version": 2,', 1), {
        'markdown_table_row_breaks': lambda value: Decision.corrected(value + ' revised', 'candidate_revision'),
    })
    before = dict(objects.contents)
    assert replay_rule_input(objects, 'thread', 'attempt', ref, bundle, candidate=candidate).value == original + ' revised'
    assert objects.contents == before
    with pytest.raises(ValueError, match='bundle mismatch'):
        replay_rule_input(objects, 'thread', 'attempt', ref, candidate)
    with pytest.raises(KeyError):
        replay_rule_input(objects, 'thread', 'other-attempt', ref, bundle)
    key = next(iter(objects.contents))
    objects.contents[key] += b' '
    with pytest.raises(ValueError, match='digest'):
        replay_rule_input(objects, 'thread', 'attempt', ref, bundle)


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


def test_candidate_review_binds_digests_and_preserves_archived_input():
    from capstone_agent.answer_correction import presentation_rule_bundle
    from capstone_agent.artifacts import MemoryObjectStore
    from capstone_agent.harness_validation import archive_rule_input, load_rule_bundle
    from capstone_agent.harness_rule_review import review_rule_candidate

    store = MemoryObjectStore()
    original = presentation_rule_bundle()
    candidate = load_rule_bundle(original.source.replace(b'"version": 1,', b'"version": 2,', 1), {
        'markdown_table_row_breaks': lambda value: Decision.corrected(value + ' revised', 'candidate_revision'),
    })
    ref = archive_rule_input(store, 'thread', 'attempt', original, 'answer', answer_limit=50)
    before = dict(store.contents)
    receipt = review_rule_candidate(store, 'thread', 'attempt', ref, original, candidate)
    assert receipt['archive_sha256'] == ref
    assert receipt['original_bundle_sha256'] == original.digest
    assert receipt['candidate_bundle_sha256'] == candidate.digest
    assert receipt['original']['value'] == 'answer'
    assert receipt['candidate']['value'] == 'answer revised'
    assert store.contents == before


def test_cross_version_review_requires_matching_archive_and_trusted_revisions():
    from capstone_agent.harness_rule_review import compare_runtime_receipts

    common = {'schema': 'capstone-validation-runtime-receipt/1', 'thread_id': 't',
              'attempt_id': 'a', 'archive_sha256': 'a' * 64, 'target': 'answer.text'}
    baseline = {**common, 'role': 'baseline', 'revision': 'b' * 40,
                'bundle_sha256': 'c' * 64, 'processors': [['engine', 'd' * 64]],
                'decision': {'status': 'accepted', 'value': 'original'}}
    candidate = {**common, 'role': 'candidate', 'revision': 'e' * 40,
                 'bundle_sha256': 'f' * 64, 'processors': [['engine', '1' * 64]],
                 'decision': {'status': 'corrected', 'value': 'corrected'}}
    review = compare_runtime_receipts(baseline, candidate, trusted_revisions={'b' * 40, 'e' * 40})
    assert review['baseline_revision'] == 'b' * 40
    assert review['candidate_bundle_sha256'] == 'f' * 64
    with pytest.raises(ValueError):
        compare_runtime_receipts(baseline, {**candidate, 'archive_sha256': '2' * 64},
                                 trusted_revisions={'b' * 40, 'e' * 40})
    with pytest.raises(ValueError):
        compare_runtime_receipts(baseline, candidate, trusted_revisions={'b' * 40})


def test_runtime_receipts_compare_installed_distinct_handlers():
    from capstone_agent.answer_correction import presentation_rule_bundle
    from capstone_agent.artifacts import MemoryObjectStore
    from capstone_agent.harness_validation import archive_rule_input, load_rule_bundle
    from capstone_agent.harness_rule_review import compare_runtime_receipts, runtime_receipt

    store = MemoryObjectStore()
    baseline = presentation_rule_bundle()
    proposed = load_rule_bundle(baseline.source.replace(b'"version": 1,', b'"version": 2,', 1), {
        'markdown_table_row_breaks': lambda value: Decision.corrected(value + ' revised', 'revised'),
    })
    ref = archive_rule_input(store, 'thread', 'attempt', baseline, 'answer', answer_limit=50)
    old = runtime_receipt(store, 'thread', 'attempt', ref, baseline, role='baseline', revision='a' * 40)
    new = runtime_receipt(store, 'thread', 'attempt', ref, proposed, role='candidate', revision='b' * 40)
    assert old['processors'] != new['processors']
    review = compare_runtime_receipts(old, new, trusted_revisions={'a' * 40, 'b' * 40})
    assert review['candidate']['value'] == 'answer revised'
    with pytest.raises(ValueError, match='bundle mismatch'):
        runtime_receipt(store, 'thread', 'attempt', ref, proposed, role='baseline', revision='b' * 40)
