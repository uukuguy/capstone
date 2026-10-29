from dataclasses import replace
from types import SimpleNamespace
from threading import Event
from capstone_agent.session_title import SessionTitle
from capstone_agent.session_title_summary import TitleSummaryScheduler
from capstone_agent.thread_service import InMemoryThreadService
from test_session_title_backfill import complete
from test_thread_postgres import _snapshot


def test_background_summary_uses_frozen_selection_and_survives_reads():
    service = InMemoryThreadService(_snapshot('thr_summary'))
    complete(service, 'thr_summary', 'att_title', '请比较三种运输方案，并把成本、交付时间、风险和建议放进报告。')
    selection = {'profile_id': 'frozen-profile'}
    calls = []
    def request(text, profile):
        calls.append((text, profile))
        return '运输方案比较', {'total_tokens': 40}
    scheduler = TitleSummaryScheduler(request)
    claim = SimpleNamespace(thread_id='thr_summary', attempt=SimpleNamespace(attempt_id='att_title'),
        instruction='请比较三种运输方案，并把成本、交付时间、风险和建议放进报告。', submission={'llm_selection': selection})
    scheduler.submit(service, claim, 'completed')
    scheduler.pool.shutdown(wait=True)
    assert calls[0][1] == selection
    assert service.snapshot('thr_summary').session_title.text == '运输方案比较'
    assert service.list_threads()['threads'][0]['session_title']['text'] == '运输方案比较'
    assert len(calls) == 1
    assert next(e for e in service._events if e.event_type == 'session_title_summary').payload['purpose'] == 'session_title'
    assert service._events[-1].event_type == 'session_title_changed'


def test_late_summary_cannot_override_user_rename():
    service = InMemoryThreadService(_snapshot('thr_race'))
    complete(service, 'thr_race', 'att_title', '比较运输方案')
    entered, release = Event(), Event()
    def request(*args):
        entered.set()
        assert release.wait(2)
        return '模型主题', {}
    scheduler = TitleSummaryScheduler(request)
    claim = SimpleNamespace(thread_id='thr_race', attempt=SimpleNamespace(attempt_id='att_title'),
        instruction='比较运输方案', submission={'llm_selection': {'profile_id': 'frozen'}})
    scheduler.submit(service, claim, 'completed')
    assert entered.wait(2)
    with service._lock:
        service._snapshot = replace(service._snapshot, session_title=SessionTitle('用户名字', 'user', 2))
    release.set()
    scheduler.pool.shutdown(wait=True)
    assert service.snapshot('thr_race').session_title.text == '用户名字'


def test_failure_is_separate_naming_event_and_does_not_change_completion():
    service = InMemoryThreadService(_snapshot('thr_failure'))
    complete(service, 'thr_failure', 'att_title', '比较运输方案')
    def fail(*args):
        raise TimeoutError('secret-canary')
    scheduler = TitleSummaryScheduler(fail)
    claim = SimpleNamespace(thread_id='thr_failure', attempt=SimpleNamespace(attempt_id='att_title'),
        instruction='比较运输方案', submission={'llm_selection': {'profile_id': 'frozen'}})
    scheduler.submit(service, claim, 'completed')
    scheduler.pool.shutdown(wait=True)
    assert service._events[-1].payload['status'] == 'failed'
    assert 'secret-canary' not in str(service._events[-1].payload)
    assert any(e.event_type == 'attempt_completed' for e in service._events)
    assert service.snapshot('thr_failure').session_title.text == '比较运输方案'


def test_completion_hook_is_opt_in_and_runs_after_completion():
    service = InMemoryThreadService(_snapshot('thr_hook'))
    calls = []
    service._title_summary_scheduler = SimpleNamespace(submit=lambda s, claim, phase: calls.append((s._snapshot.current_attempt, phase)))
    receipt = service.submit_command({'schema': 'capstone-command/1', 'command_id': 'cmd_hook',
        'idempotency_key': 'hook', 'thread_id': 'thr_hook', 'run_id': 'run_test_001',
        'kind': 'send_auto', 'expected_event_seq': 0, 'payload': {'text': '比较运输方案'}})
    assert receipt.status == 'accepted'
    claim = service.claim_attempt('title-test', 30)
    service.finish_attempt(claim, phase='completed', payload={'answer': '完成'})
    assert calls == [(None, 'completed')]


def test_actual_request_uses_frozen_profile_without_tools(monkeypatch):
    import httpx
    import json
    from capstone_agent.session_title_summary import request_summary
    from capstone_agent.workbench_llm_profiles import ProfileRegistry
    selection = ProfileRegistry(environment={}).freeze('intranet-dsv4-18804')
    seen = []
    def handler(request):
        document = json.loads(request.content)
        seen.append((str(request.url), document))
        return httpx.Response(200, json={'choices': [{'message': {'content': '运输方案比较'}}], 'usage': {'total_tokens': 20}})
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler)))
    result = request_summary('比较三种运输方案的成本和时间', selection)
    assert result[:2] == ('运输方案比较', {'total_tokens': 20})
    assert len(result[2]) == 64
    assert seen[0][0] == 'http://192.168.72.69:18804/v1/chat/completions'
    assert seen[0][1]['model'] == 'dsv4'
    assert seen[0][1]['max_tokens'] == 64
    assert 'tools' not in seen[0][1]


def test_late_summary_cannot_override_a_newer_instruction():
    from capstone_agent.session_title_summary import _persist
    service = InMemoryThreadService(_snapshot('thr_newer'))
    complete(service, 'thr_newer', 'att_old', '比较运输方案')
    complete(service, 'thr_newer', 'att_new', '解释彩虹形成原因')
    claim = SimpleNamespace(thread_id='thr_newer', attempt=SimpleNamespace(attempt_id='att_old'))
    _persist(service, claim, '旧的运输主题', {'status': 'completed'})
    assert service.snapshot('thr_newer').session_title.text == '解释彩虹形成原因'


from test_thread_postgres import postgres_thread_service


def test_postgres_summary_persists_after_background_completion(postgres_thread_service):
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))
    complete(service, thread_id, 'att_summary', '比较运输成本与时间')
    scheduler = TitleSummaryScheduler(lambda *args: ('运输方案比较', {'total_tokens': 12}))
    claim = SimpleNamespace(thread_id=thread_id, attempt=SimpleNamespace(attempt_id='att_summary'),
        instruction='比较运输成本与时间', submission={'llm_selection': {'profile_id': 'frozen'}})
    scheduler.submit(service, claim, 'completed')
    scheduler.pool.shutdown(wait=True)
    assert service.snapshot(thread_id).session_title.text == '运输方案比较'


def test_title_request_uses_registered_options_and_keeps_truncated_usage(monkeypatch):
    import httpx
    import json
    import pytest
    from capstone_agent.session_title_summary import request_summary, TitleSummaryFailure
    from capstone_agent.workbench_llm_profiles import ProfileRegistry
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'fixture-key')
    selected = ProfileRegistry().freeze('commercial-deepseek-flash')
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={'choices': [{'finish_reason': 'length', 'message': {'content': '', 'reasoning_content': 'not retained'}}], 'usage': {'completion_tokens': 64, 'total_tokens': 118}})
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler)))
    with pytest.raises(TitleSummaryFailure) as error:
        request_summary('经营数据报告', selected)
    assert calls[0]['thinking'] == {'type': 'disabled'}
    assert len(calls) == 1
    assert error.value.code == 'title_output_truncated'
    assert error.value.usage == {'completion_tokens': 64, 'total_tokens': 118}


def test_summary_input_preserves_initial_and_recent_topics_with_bounded_history():
    from capstone_agent.session_title_summary import summary_input
    service = InMemoryThreadService(_snapshot('thr_topics'))
    complete(service, 'thr_topics', 'att_first', '比较运输方式的成本')
    for i in range(10):
        complete(service, 'thr_topics', f'att_middle_{i}', '补充信息' + str(i) + '要求' * 600)
    complete(service, 'thr_topics', 'att_last', '再加入仓储成本和交付时间评估')
    claim = SimpleNamespace(thread_id='thr_topics', attempt=SimpleNamespace(attempt_id='att_last'))
    text = summary_input(service, claim)
    assert '比较运输方式的成本' in text
    assert '仓储成本和交付时间评估' in text
    assert 'may be omitted' in text
    assert len(text) <= 4096
