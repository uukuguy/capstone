"""Offline contracts for the issue automation control plane."""
import dataclasses
import json
import os
from pathlib import Path

import pytest

from tools.issue_automation.policy import Policy, command, feedback, public_text, safe_path
from tools.issue_automation.store import Store


def test_minimal_feedback_and_bot_dedupe():
    issue = {"number": 1, "title": "问题", "body": "![截图](https://github.com/user-attachments/assets/a)", "comments": []}
    result = feedback(issue)
    assert result["environment"] == "cloud-demo"
    assert result["version"] is None
    assert result["images"]
    issue["comments"].append({"user": {"type": "Bot", "login": "ai[bot]"}, "body": "机器人"})
    assert feedback(issue)["input_hash"] == result["input_hash"]
    issue["comments"].append({"user": {"type": "User", "login": "u"}, "body": "local-demo 刷新后发生"})
    assert feedback(issue)["environment"] == "local-demo"
    assert feedback(issue)["input_hash"] != result["input_hash"]


def test_fixed_commands_and_public_output():
    assert command("/ai fix", "write") == "fix"
    assert command("/ai fix", "read") is None
    assert command("/ai deploy", "admin") is None
    assert command("/ai fix; touch /tmp/pwn", "admin") is None
    with pytest.raises(ValueError):
        public_text("OPENAI_API_KEY=sk-secret-secret-secret")
    with pytest.raises(ValueError):
        safe_path("../../.env", ("packages/",))
    with pytest.raises(ValueError):
        safe_path("packages/app/.env", ("packages/",))


def test_private_queue_dedupe_lease_recovery_and_pause(tmp_path):
    store = Store(tmp_path / "state" / "queue.sqlite")
    task = store.enqueue(1, "input", "policy", "source")
    assert store.enqueue(1, "input", "policy", "source") == task
    store.update(task, state="ready")
    assert store.claim(task, "worker", now=10, seconds=5)
    assert not store.claim(task, "other", now=11, seconds=5)
    second = store.enqueue(2, "other", "policy", "source")
    store.update(second, state="ready")
    assert not store.claim(second, "other", now=11, seconds=5)
    assert store.claim(task, "restarted", now=16, seconds=5)
    store.pause(1)
    assert not store.claim(task, "other", now=30, seconds=5)
    assert os.stat(store.path).st_mode & 0o777 == 0o600


def test_atomic_cost_reservation_survives_restart(tmp_path):
    store = Store(tmp_path / "queue.sqlite")
    task = store.enqueue(1, "input", "policy", "source")
    assert store.reserve(task, "request", 0.4, task_limit=0.5, day_limit=1)
    assert not store.reserve(task, "second", 0.2, task_limit=0.5, day_limit=1)
    store.close()
    resumed = Store(tmp_path / "queue.sqlite")
    assert not resumed.reserve(task, "request", 0.4, task_limit=0.5, day_limit=1)
    assert resumed.cost(task) == pytest.approx(0.4)


def test_atomic_token_budget_refuses_over_limit(tmp_path):
    store = Store(tmp_path / "q.sqlite")
    task = store.enqueue(1, "input", "policy", "source")
    assert store.reserve(task, "one", 0.1, 1, 2, tokens=100, task_token_limit=150, day_token_limit=300)
    assert not store.reserve(task, "two", 0.1, 1, 2, tokens=100, task_token_limit=150, day_token_limit=300)



def test_policy_disables_calls_and_rejects_untrusted_endpoint():
    policy = Policy()
    assert not policy.model_enabled
    assert not policy.write_enabled
    assert policy.execution_owner == "local"
    with pytest.raises(ValueError):
        dataclasses.replace(policy, endpoint="http://127.0.0.1:8080/v1").validate()
    with pytest.raises(ValueError):
        dataclasses.replace(policy, max_rounds=100).validate()
