import pytest

from capstone_agent.session_title import SessionTitle


def test_manual_same_name_claims_ownership_and_survives_restore():
    initial = SessionTitle('电网分析与决策')
    manual = initial.rename(initial.text, expected_revision=0)
    restored = SessionTitle.from_document(manual.to_document())
    assert restored.source == 'user'
    assert restored.suggest('新的分析', expected_revision=1, source_ref='artifact_2') == restored


def test_late_automatic_candidate_cannot_overwrite_manual_title():
    manual = SessionTitle('企业研究与分析').rename('季度研究', expected_revision=0)
    assert manual.suggest('旧候选', expected_revision=0, source_ref='artifact_1') == manual


def test_stale_candidates_and_repeated_titles_do_not_churn_revision():
    title = SessionTitle('企业研究与分析').suggest('月度研究', expected_revision=0, source_ref='artifact_1')
    assert title.source == 'automatic' and title.revision == 1
    assert title.suggest('旧研究', expected_revision=0, source_ref='artifact_0') == title
    assert title.suggest(title.text, expected_revision=1, source_ref='artifact_2') == title
    assert SessionTitle.from_document(title.to_document()) == title


def test_manual_conflict_and_blank_title_preserve_original():
    title = SessionTitle('通用聊天')
    with pytest.raises(ValueError, match='revision conflict'):
        title.rename('新标题', expected_revision=1)
    with pytest.raises(ValueError):
        title.rename('   ', expected_revision=0)
    assert title.revision == 0


@pytest.mark.parametrize('patch', [{'revision': True}, {'source': 'guessed'}, {'text': ''}, {'unexpected': 1}])
def test_invalid_persisted_title_is_rejected(patch):
    with pytest.raises(ValueError):
        SessionTitle.from_document({**SessionTitle('研究').to_document(), **patch})
