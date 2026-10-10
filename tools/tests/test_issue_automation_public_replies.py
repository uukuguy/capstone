from dataclasses import replace
from types import SimpleNamespace

import pytest

from tools.issue_automation.model import validate_triage
from tools.issue_automation.service import Service, triage_reply
from tools.issue_automation.policy import Policy
from tools.issue_automation.store import Store


def judgment(state="ready", **changes):
    return {"summary": "内部诊断摘要", "type": "bug", "state": state,
            "facts": ["内部结果引用检查"], "hypotheses": ["证据接纳缺口"],
            "questions": [], "acceptance": "计算完成后直接回答用户问题",
            "environment": "cloud-demo", "visible_version": None, **changes}


@pytest.mark.parametrize("state", ["ready", "blocked"])
def test_triage_does_not_justify_public_progress(state):
    with pytest.raises(ValueError, match="does not justify"):
        triage_reply(judgment(state))


def test_missing_information_reply_contains_only_specific_questions():
    question = "是在刷新后发生，还是连续对话时发生？"
    assert triage_reply(judgment("needs-info", questions=[question])) == question


@pytest.mark.parametrize("questions", [[], [""], ["   "], ["Only English"]])
def test_missing_information_requires_useful_chinese_questions(questions):
    with pytest.raises(ValueError):
        validate_triage(judgment("needs-info", questions=questions))


def service_at(tmp_path):
    comments = []
    github = SimpleNamespace(
        issue=lambda number: {"number": number, "title": "没有正式回答", "body": "请检查", "comments": []},
        publish_comment=lambda *args: comments.append(args[-1]))
    store = Store(tmp_path / "state.sqlite")
    service = Service(replace(Policy(), write_enabled=True), store, github, None, SimpleNamespace(sha="a" * 40), None)
    return service, store, comments


@pytest.mark.parametrize("state", ["ready", "blocked"])
def test_internal_triage_is_saved_without_comment(tmp_path, state):
    service, store, comments = service_at(tmp_path)
    task = service.triage(1, judgment(state))
    assert store.get(task)["state"] == state
    assert comments == []


def test_only_missing_information_is_published(tmp_path):
    service, _, comments = service_at(tmp_path)
    question = "请提供出现问题时输入的那条指令。"
    service.triage(1, judgment("needs-info", questions=[question]))
    assert comments == [question]


@pytest.mark.parametrize("state", ["working", "review"])
def test_cached_triage_does_not_comment_or_reclassify_active_work(tmp_path, state):
    service, store, comments = service_at(tmp_path)
    task, _, _ = service.intake(1)
    store.update(task, state=state, payload={"triage": judgment()})
    service.triage(1)
    assert store.get(task)["state"] == state and comments == []
    with pytest.raises(ValueError, match="active or reviewed"):
        service.triage(1, judgment())


def test_explicit_judgment_refreshes_legacy_blocked_cache(tmp_path):
    service, store, comments = service_at(tmp_path)
    task, _, _ = service.intake(1)
    store.update(task, state="blocked", payload={"triage": judgment("blocked")})
    service.triage(1, judgment())
    assert store.get(task)["state"] == "ready" and comments == []
