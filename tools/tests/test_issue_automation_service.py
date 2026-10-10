import dataclasses
import json
from pathlib import Path
import subprocess

import pytest

from tools.issue_automation.policy import Policy
from tools.issue_automation.store import Store
from tools.issue_automation.repair import Source, DockerSandbox, Repair
from tools.issue_automation.service import Service, release_status


class FakeGitHub:
    def __init__(self):
        self.value = {"number": 7, "title": "按钮异常", "body": "![图](https://github.com/user-attachments/assets/id)", "comments": []}
        self.comments = []
        self.prs = []
    def issue(self, number):
        return self.value
    def issues(self):
        return [self.value]
    def permission(self, user):
        return "write" if user == "maintainer" else "read"
    def publish_comment(self, store, task, issue, kind, body):
        key = task + ":" + kind
        if not store.action(key):
            self.comments.append(body)
            store.record_action(key, task, "done", {"id": len(self.comments)})
    def find_pr(self, branch):
        return next((p for p in self.prs if p["head"]["ref"] == branch), None)
    def publish_candidate(self, store, task, branch, source_sha, files, title, body):
        existing = self.find_pr(branch)
        if existing:
            return existing
        self.prs.append({"number": 10, "state": "open", "base": {"ref": "main"}, "html_url": "https://github.com/uukuguy/capstone/pull/10", "head": {"ref": branch, "sha": "candidate"}, "body": body})
        return self.prs[-1]


class FakeModel:
    def request(self, task, purpose, context, images=()):
        if purpose == "triage":
            info = not context["feedback"]["comments"]
            return {"summary": "AI：按钮异常", "state": "needs-info" if info else "ready", "type": "bug", "facts": ["截图中的按钮异常"], "hypotheses": [], "questions": ["刷新后发生吗？"] if info else [], "environment": "cloud-demo", "visible_version": None, "acceptance": "点击按钮后可以读取历史"}
        if purpose == "select":
            return {"paths": ["packages/capstone-app/app.py"]}
        return {"summary": "修复按钮行为", "reproduction_check": 0, "files": [{"path": "packages/capstone-app/app.py", "content": "print('fixed')\n"}]}


def repository(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(root)], check=True, capture_output=True)
    target = root / "packages/capstone-app/app.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('broken')\n")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "base"], check=True, capture_output=True)
    return Source(root, "main")


class FakeSandbox:
    def run(self, root, checks, seconds):
        return {"passed": "fixed" in (root / "packages/capstone-app/app.py").read_text(), "checks": [{"exit_code": 0 if "fixed" in (root / "packages/capstone-app/app.py").read_text() else 1}]}


def test_triage_reply_maintainer_fix_and_restart_pr_recovery(tmp_path):
    policy = dataclasses.replace(Policy(), model_enabled=True, write_enabled=True, model="fake", task_budget_usd=2, daily_budget_usd=3, request_reserve_usd=0.2, checks=(("python", "test.py"),), sandbox_image="trusted@sha256:" + "1" * 64)
    store = Store(tmp_path / "state/q.sqlite")
    source = repository(tmp_path)
    github = FakeGitHub()
    repair = Repair(policy, source, FakeModel(), FakeSandbox(), tmp_path / "candidates")
    service = Service(policy, store, github, FakeModel(), source, repair)
    first = service.triage(7)
    assert store.get(first)["state"] == "needs-info"
    service.triage(7)
    assert len(github.comments) == 1
    github.value["comments"] = [{"id": 1, "body": "刷新后发生", "user": {"login": "user", "type": "User"}}, {"id": 2, "body": "/ai fix", "user": {"login": "maintainer", "type": "User"}}]
    service.scan()
    assert github.prs == []  # A comment records intent; it never starts repair.
    service.triage(7)
    service.fix(7)
    task = store.list(7)[0]
    assert task["state"] == "review"
    assert len(github.prs) == 1
    assert "local-dev" in github.prs[0]["body"] and "待验证" in github.prs[0]["body"]
    store.update(task["task_id"], state="working", lease_until=0)
    service.fix(7)
    assert len(github.prs) == 1


def test_candidate_paths_and_docker_environment_are_bounded(tmp_path):
    source = repository(tmp_path)
    with pytest.raises(ValueError):
        source.read("../../.env", Policy())
    calls = []
    sandbox = DockerSandbox(dataclasses.replace(Policy(), sandbox_image="trusted@sha256:" + "1" * 64), runner=lambda args, **kw: calls.append((args, kw)) or subprocess.CompletedProcess(args, 1 if args[1] == "inspect" else 0, b"", b""))
    sandbox.run(tmp_path, (("python", "test.py"),), 20)
    args, options = calls[0]
    assert "--network=none" in args and "--read-only" in args
    assert not any("TOKEN" in a or "API_KEY" in a for a in args)
    assert set(options["env"]) <= {"PATH", "DOCKER_HOST", "HOME", "LANG"}


def test_sandbox_daemon_failure_cannot_confirm_cleanup(tmp_path):
    def runner(args, **kwargs):
        return subprocess.CompletedProcess(args, 0 if args[1] == "run" else 1, b"", b"")
    sandbox = DockerSandbox(dataclasses.replace(Policy(), sandbox_image="sha256:" + "1" * 64), runner=runner)
    with pytest.raises(RuntimeError, match="cleanup"):
        sandbox.run(tmp_path, (("python", "test.py"),), 20)


def test_release_never_claims_demo_for_main_merge_or_missing_tag():
    result = release_status({"merged": True, "merge_commit_sha": "a" * 40}, None, None, "cloud-demo")
    assert result["state"] == "release-pending"
    assert result["deployed"] is False
    receipt = {"stage": "demo", "source_sha": "a" * 40, "tag": "demo-20261010-1200-aaaaaaa", "passed": True, "checks": {"ready": True, "app": True, "case": True, "identity": True}, "deployment_ids": ["deployment"]}
    tag = {"name": receipt["tag"], "type": "tag", "source_sha": "a" * 40, "annotation": receipt}
    assert release_status({"merged": True, "merge_commit_sha": "a" * 40}, tag, receipt, "cloud-demo")["deployed"]
    assert not release_status({"merged": True, "merge_commit_sha": "a" * 40}, {**tag, "type": "commit"}, receipt, "cloud-demo")["deployed"]
    later = {**receipt, "source_sha": "b" * 40}
    later_tag = {**tag, "source_sha": "b" * 40, "annotation": later}
    assert release_status({"merged": True, "merge_commit_sha": "a" * 40}, later_tag, later, "cloud-demo", contains_merge=True)["deployed"]
    legacy = {"name": "demo-20261010-1231-aaaaaaa", "type": "tag", "source_sha": "a" * 40, "format": "legacy-text", "annotation": None}
    result = release_status({"merged": True, "merge_commit_sha": "a" * 40}, legacy, None, "cloud-demo")
    assert result["deployed"] is False
    assert result["tag_status"] == "legacy-report-required"


def test_manual_current_session_flow_needs_no_model_key(tmp_path):
    source = repository(tmp_path)
    policy = dataclasses.replace(Policy(), write_enabled=True, checks=(("python", "test.py"),))
    store = Store(tmp_path / "state/q.sqlite")
    github = FakeGitHub()
    model = FakeModel()
    judgment = model.request("", "triage", {"feedback": {"comments": ["reply"]}})
    repair = Repair(policy, source, None, FakeSandbox(), tmp_path / "candidates")
    service = Service(policy, store, github, None, source, repair)
    task = service.triage(7, judgment)
    prepared = service.begin(7, ["packages/capstone-app/app.py"])
    assert prepared["task_id"] == task
    assert "broken" in prepared["files"]["packages/capstone-app/app.py"]
    candidate = service.complete(task, {"summary": "修复按钮行为", "reproduction_check": 0, "files": [{"path": "packages/capstone-app/app.py", "content": "print('fixed')\n"}]})
    assert candidate["number"] == 10
    assert store.get(task)["state"] == "review"
    assert not policy.model_enabled


def test_failed_manual_candidate_cannot_publish(tmp_path):
    source = repository(tmp_path)
    policy = dataclasses.replace(Policy(), write_enabled=True, checks=(("python", "test.py"),))
    store = Store(tmp_path / "state/q.sqlite")
    github = FakeGitHub()
    repair = Repair(policy, source, None, FakeSandbox(), tmp_path / "candidates")
    service = Service(policy, store, github, None, source, repair)
    service.triage(7, FakeModel().request("", "triage", {"feedback": {"comments": ["reply"]}}))
    prepared = service.begin(7, ["packages/capstone-app/app.py"])
    with pytest.raises(ValueError, match="failed"):
        service.complete(prepared["task_id"], {"summary": "修复按钮行为", "reproduction_check": 0, "files": [{"path": "packages/capstone-app/app.py", "content": "print('still broken')\n"}]})
    assert github.prs == []


def test_manual_repair_can_add_selected_regression_test(tmp_path):
    source = repository(tmp_path)
    policy = dataclasses.replace(Policy(), checks=(("python", "test.py"),))
    repair = Repair(policy, source, None, FakeSandbox(), tmp_path / "candidates")
    prepared = repair.prepare("task", ["packages/capstone-app/app.py", "packages/capstone-app/tests/test_history.py"])
    assert prepared["files"]["packages/capstone-app/tests/test_history.py"] == ""
    result = repair.validate_manual("task", {"summary": "修复按钮行为", "reproduction_check": 0, "files": [{"path": "packages/capstone-app/app.py", "content": "print('fixed')\n"}, {"path": "packages/capstone-app/tests/test_history.py", "content": "def test_history():\n    assert True\n"}]})
    assert "packages/capstone-app/tests/test_history.py" in result["files"]


def test_manual_judgment_cannot_override_explicit_feedback_environment(tmp_path):
    source = repository(tmp_path)
    github = FakeGitHub()
    github.value["body"] = "环境：local-demo，历史异常"
    service = Service(Policy(), Store(tmp_path / "q.sqlite"), github, None, source, None)
    judgment = FakeModel().request("", "triage", {"feedback": {"comments": []}})
    task = service.triage(7, judgment)
    assert service.store.get(task)["payload"]["triage"]["environment"] == "local-demo"


@pytest.mark.parametrize("path,old,new", [
    ("packages/capstone-app/src/history.test.ts", "test('history', () => { expect(true).toBe(true) });\n", "// disabled\n"),
    ("packages/capstone-app/tests/test_history.py", "def test_history():\n    assert False\n", "def test_history():\n    pass\n"),
    ("packages/capstone-app/package.json", '{"scripts":{"test":"vitest"}}', '{"scripts":{"test":"true"}}'),
    ("packages/capstone-app/src/testSetup.ts", "globalThis.ResizeObserver = class {};\n", "// remove setup\n"),
])
def test_candidate_cannot_weaken_tests_or_gate_configuration(tmp_path, path, old, new):
    source = repository(tmp_path)
    target = source.root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(old)
    subprocess.run(["git", "-C", str(source.root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(source.root), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "test"], check=True, capture_output=True)
    repair = Repair(dataclasses.replace(Policy(), checks=(("python", "test.py"),)), Source(source.root), None, FakeSandbox(), tmp_path / "candidate")
    repair.prepare("task", [path])
    with pytest.raises(ValueError, match="protected|unchanged"):
        repair.validate_manual("task", {"summary": "修复行为", "reproduction_check": 0, "files": [{"path": path, "content": new}]})
