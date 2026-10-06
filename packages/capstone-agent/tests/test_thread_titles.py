from __future__ import annotations

import pytest

from test_thread_worker import _service, _submit, _Runtime
from capstone_agent.thread_worker import run_pending_attempt


class TitledRuntime(_Runtime):
    def generate_thread_title(self, question, answer):
        assert question == 'inspect' and answer == 'done'
        return 'IEEE-39 电网运行分析'


def test_successful_turn_gets_a_persistent_title_without_changing_answer():
    service = _service()
    _submit(service)
    result = run_pending_attempt(service, lambda _: TitledRuntime(), worker_id='worker')
    assert result.status == 'completed' and result.answer == 'done'
    metadata = service.thread_metadata('thr_worker')
    assert metadata['title'] == 'IEEE-39 电网运行分析'
    assert metadata['model_id'] == 'ieee39'
    assert service.list_threads()['threads'][0]['title'] == metadata['title']
    assert service.set_archived('thr_worker', True)['title'] == metadata['title']
    assert service.read_events('thr_worker', 0).events[-1].payload['answer'] == 'done'


def test_title_failure_preserves_the_completed_turn():
    class BrokenTitle(TitledRuntime):
        def generate_thread_title(self, *_):
            raise RuntimeError('provider unavailable')
    service = _service()
    _submit(service)
    result = run_pending_attempt(service, lambda _: BrokenTitle(), worker_id='worker')
    assert result.status == 'completed'
    assert service.thread_metadata('thr_worker')['title'] is None


def test_existing_title_is_preserved_and_skips_generation():
    service = _service()
    _submit(service)
    run_pending_attempt(service, lambda _: TitledRuntime(), worker_id='worker')
    assert service.set_thread_title('thr_worker', 'different', 'unknown_attempt') is False
    assert service.thread_metadata('thr_worker')['title'] == 'IEEE-39 电网运行分析'
    snapshot = service.snapshot('thr_worker')
    service.submit_command({'schema': 'capstone-command/1', 'command_id': 'cmd_second',
        'idempotency_key': 'idem_second', 'thread_id': 'thr_worker', 'run_id': 'run_worker',
        'kind': 'send_ordinary', 'expected_event_seq': snapshot.last_event_seq, 'payload': {'text': 'inspect'}})
    class NoRepeat(TitledRuntime):
        def generate_thread_title(self, *_):
            pytest.fail('An existing title must not trigger another Provider request')
    assert run_pending_attempt(service, lambda _: NoRepeat(), worker_id='worker').status == 'completed'


@pytest.mark.parametrize('value', ['', 'x' * 81, 'title\nsecond line', '<script>bad</script>'])
def test_invalid_titles_are_rejected(value):
    from capstone_agent.thread_titles import normalize_thread_title
    assert normalize_thread_title(value) is None


def test_generated_title_is_plain_text():
    from capstone_agent.thread_titles import normalize_thread_title
    assert normalize_thread_title('“PyPSA 经济调度与潮流校验”') == 'PyPSA 经济调度与潮流校验'


def test_title_request_has_no_extension_tools_or_authority_context(monkeypatch, tmp_path):
    import json
    from types import SimpleNamespace
    import capstone_agent.thread_titles as titles
    seen = {}
    def launch(llm, paths, **kwargs):
        assert paths.extension_path is None and paths.runtime_descriptor_path is None
        assert paths.tool_catalog_path is None and paths.domain_search_paths == ()
        seen['policy'] = paths.system_policy_path.read_text()
        return 'isolated-title-launch'
    class Client:
        def __init__(self, command, workspace, trace, **kwargs):
            assert command == 'isolated-title-launch' and kwargs['timeout_seconds'] == 12
        def start(self): pass
        def prompt_and_wait(self, text):
            seen['input'] = json.loads(text)
            return 'PyPSA 经济调度与潮流校验'
        def stop(self): seen['stopped'] = True
    monkeypatch.setattr(titles, 'build_pi_launch', launch)
    monkeypatch.setattr(titles, 'PiRpcClient', Client)
    host = SimpleNamespace(command=None, project_pi_dir=tmp_path)
    generate = titles.ThreadTitleGenerator(host, SimpleNamespace(secret=None), tmp_path, tmp_path / 'title')
    assert generate('q' * 5000, 'a' * 10000) == 'PyPSA 经济调度与潮流校验'
    assert len(seen['input']['user']) == 2000 and len(seen['input']['assistant']) == 3000
    assert seen['stopped'] is True
