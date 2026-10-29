from dataclasses import replace
import pytest
from capstone_agent.session_title import SessionTitle
from capstone_agent.session_title_maintenance import maintenance_selection, maintain_one
from capstone_agent.workbench_llm_profiles import ProfileRegistry
from capstone_agent.thread_service import InMemoryThreadService
from test_session_title_backfill import complete
from test_thread_postgres import _snapshot


def test_intranet_history_is_never_sent_to_commercial_fallback():
    registry = ProfileRegistry(environment={'DEEPSEEK_API_KEY': 'fixture'})
    selected = registry.freeze('intranet-dsv4-18804')
    with pytest.raises(ValueError):
        maintenance_selection({'llm_selection': selected}, registry, 'commercial-deepseek-flash')
    assert maintenance_selection({}, registry, 'commercial-deepseek-flash')['profile_id'] == 'commercial-deepseek-flash'


def fixture():
    title = SessionTitle('旧的自动标题内容' * 8, 'automatic', 1, 'completed:att:2')
    service = InMemoryThreadService(replace(_snapshot('thr_maintenance'), session_title=title))
    complete(service, 'thr_maintenance', 'att', '比较运输成本和交付时间')
    row = {'thread_id': 'thr_maintenance', 'attempt_id': 'att', 'session_title': title.to_document(), 'submission_snapshot': {}}
    registry = ProfileRegistry(environment={'DEEPSEEK_API_KEY': 'fixture'})
    return service, row, registry, title


def test_maintenance_failure_keeps_old_title():
    service, row, registry, title = fixture()
    def fail(*args):
        raise TimeoutError('secret-canary')
    result = maintain_one(service, row, registry, 'commercial-deepseek-flash', request=fail)
    assert result['status'] == 'failed'
    assert 'secret-canary' not in str(result)
    assert service._snapshot.session_title == title


def test_maintenance_success_and_concurrent_user_rename():
    service, row, registry, title = fixture()
    result = maintain_one(service, row, registry, 'commercial-deepseek-flash', request=lambda *args: ('运输方案评估', {'total_tokens': 20}, 'a'*64))
    assert result['status'] == 'completed'
    assert service.snapshot('thr_maintenance').session_title.text == '运输方案评估'
    service, row, registry, title = fixture()
    def rename(*args):
        service._snapshot = replace(service._snapshot, session_title=title.rename('用户名字', expected_revision=1))
        return '不应覆盖', {}, 'b'*64
    assert maintain_one(service, row, registry, 'commercial-deepseek-flash', request=rename)['status'] == 'deferred'
    assert service._snapshot.session_title.source == 'user'
