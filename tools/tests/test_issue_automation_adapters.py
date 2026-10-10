import dataclasses
import json
from pathlib import Path

import pytest

from tools.issue_automation.github import GitHub
from tools.issue_automation.model import Model, validate_triage, attachment_url
from tools.issue_automation.policy import Policy
from tools.issue_automation.store import Store


def test_vision_host_boundary_and_triage_contract():
    policy = Policy()
    assert attachment_url("https://github.com/user-attachments/assets/id", policy)
    for url in ("http://127.0.0.1/a", "https://github.com.evil/a", "https://github.com/private/token", "https://user-images.githubusercontent.com/a?token=x"):
        with pytest.raises(ValueError):
            attachment_url(url, policy)
    result = validate_triage({"summary": "AI：历史浏览异常", "type": "bug", "state": "needs-info", "facts": ["截图中有错误"], "hypotheses": [], "questions": ["刷新后会发生吗？"], "acceptance": "历史记录可以打开", "environment": "cloud-demo", "visible_version": None})
    assert result["visible_version"] is None
    with pytest.raises(ValueError):
        validate_triage({**result, "questions": ["一", "二", "三"]})


def test_model_disabled_does_not_send_request(tmp_path):
    calls = []
    model = Model(Policy(), Store(tmp_path / "q.sqlite"), transport=lambda *args: calls.append(args))
    with pytest.raises(ValueError, match="disabled"):
        model.request("task", "triage", {"body": "hello"})
    assert calls == []


def test_github_uncertain_comment_reconciles_before_retry(tmp_path):
    store = Store(tmp_path / "q.sqlite")
    task = store.enqueue(1, "input", "policy", "source")
    comments = []
    calls = []
    def api(method, path, data=None):
        calls.append((method, path, data))
        if path == "app":
            return {"id": 123, "slug": "trusted-bot"}
        if path == "app/installations/123":
            return {"id": 123, "app_id": 123, "app_slug": "trusted-bot"}
        if path.endswith("access_tokens"):
            return {"token": "fake-installation-token"}
        if path == "installation/repositories?per_page=100":
            return {"repositories": [{"full_name": "uukuguy/capstone"}]}
        if method == "GET":
            return comments
        comments.append({"id": 42, "body": data["body"], "user": {"login": "trusted-bot[bot]"}})
        raise TimeoutError("response lost")
    github = GitHub(Policy(write_enabled=True, publisher_login="trusted-bot[bot]", publisher_app_id=123, publisher_installation_id=123), api=api, publisher_api=api)
    with pytest.raises(TimeoutError):
        github.publish_comment(store, task, 1, "triage", "AI：已收到反馈。")
    assert github.publish_comment(store, task, 1, "triage", "AI：已收到反馈。") == 42
    assert len([c for c in calls if c[0] == "POST" and "/issues/" in c[1]]) == 1
    assert store.db.execute("SELECT state FROM actions").fetchone()[0] == "done"


def test_comment_dedupe_survives_new_policy_commit(tmp_path):
    store = Store(tmp_path / "q.sqlite")
    first = store.enqueue(1, "same-input", "policy-old", "source")
    second = store.enqueue(1, "same-input", "policy-new", "source")
    comments = []
    def api(method, path, data=None):
        if path == "app":
            return {"id": 123, "slug": "trusted-bot"}
        if path == "app/installations/123":
            return {"id": 123, "app_id": 123, "app_slug": "trusted-bot"}
        if path.endswith("access_tokens"):
            return {"token": "fake-installation-token"}
        if path == "installation/repositories?per_page=100":
            return {"repositories": [{"full_name": "uukuguy/capstone"}]}
        if method == "GET":
            return comments
        comment = {"id": len(comments) + 1, "body": data["body"], "user": {"login": "trusted-bot[bot]"}}
        comments.append(comment)
        return comment
    github = GitHub(Policy(write_enabled=True, publisher_login="trusted-bot[bot]", publisher_app_id=123, publisher_installation_id=123), api=api, publisher_api=api)
    github.publish_comment(store, first, 1, "triage", "AI：刷新后发生吗？")
    github.publish_comment(store, second, 1, "triage", "AI：刷新后发生吗？")
    assert len(comments) == 1


def test_required_ci_rejects_one_failed_or_missing_matrix_job():
    sha = "a" * 40
    rows = [{"name": "verify (ubuntu, 3.12)", "status": "completed", "conclusion": "success", "head_sha": sha}, {"name": "verify (macos, 3.14)", "status": "completed", "conclusion": "failure", "head_sha": sha}]
    github = GitHub(Policy(), api=lambda *args: {"check_runs": rows})
    assert not all(github.checks(sha).values())
    rows[:] = rows[:1]
    assert not all(github.checks(sha).values())
    rows[:] = [{"name": name, "status": "completed", "conclusion": "success", "head_sha": sha, "app": {"slug": "github-actions", "owner": {"login": "github"}}, "check_suite": {"id": 1}} for name in Policy().required_ci]
    assert all(github.checks(sha).values())
    rows[-1]["app"]["slug"] = "other-app"
    assert not all(github.checks(sha).values())


def test_raw_image_authorization_is_exact_and_redirects_fail():
    from tools.issue_automation.model import NoRedirect
    allowed = "https://raw.githubusercontent.com/uukuguy/capstone/" + "a" * 40 + "/docs/image.png"
    policy = dataclasses.replace(Policy(), attachment_urls=(allowed,))
    assert attachment_url(allowed, policy) == allowed
    with pytest.raises(ValueError):
        attachment_url(allowed.replace("image.png", "other.png"), policy)
    with pytest.raises(ValueError):
        NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://127.0.0.1/private")


def test_personal_or_mismatched_publisher_is_refused(tmp_path):
    store = Store(tmp_path / "q.sqlite")
    task = store.enqueue(1, "input", "policy", "source")
    for login, app_id in (("uukuguy", 123), ("trusted-bot[bot]", 99)):
        calls = []
        def api(method, path, data=None):
            calls.append((method, path))
            return {"id": 123, "slug": "trusted-bot"}
        github = GitHub(Policy(write_enabled=True, publisher_login=login, publisher_app_id=app_id, publisher_installation_id=123), api=api, publisher_api=api)
        with pytest.raises(ValueError, match="publisher"):
            github.publish_comment(store, task, 1, "triage", "AI：已收到反馈。")
        assert not any(method == "POST" for method, path in calls)


def test_publisher_never_inherits_personal_token(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "personal-token")
    monkeypatch.delenv("CAPSTONE_ISSUE_GITHUB_APP_JWT", raising=False)
    github = GitHub(Policy(write_enabled=True, publisher_login="trusted-bot[bot]", publisher_app_id=123, publisher_installation_id=123))
    with pytest.raises(ValueError, match="publisher"):
        github.require_write()


def test_bot_can_create_issue_without_starting_repair(tmp_path):
    store = Store(tmp_path / "q.sqlite")
    issues = []
    calls = []
    def api(method, path, data=None):
        calls.append((method, path))
        if path == "app":
            return {"id": 123, "slug": "trusted-bot"}
        if path == "app/installations/123":
            return {"id": 123, "app_id": 123, "app_slug": "trusted-bot"}
        if path.endswith("access_tokens"):
            return {"token": "fake-installation-token"}
        if path == "installation/repositories?per_page=100":
            return {"repositories": [{"full_name": "uukuguy/capstone"}]}
        if method == "GET":
            return issues
        issue = {"number": 1, "body": data["body"], "title": data["title"], "user": {"login": "trusted-bot[bot]"}}
        issues.append(issue)
        return issue
    github = GitHub(Policy(write_enabled=True, publisher_login="trusted-bot[bot]", publisher_app_id=123, publisher_installation_id=123), api=api, publisher_api=api)
    first = github.create_issue(store, "历史浏览异常", "按用户反馈整理：只发截图也可以。")
    assert github.create_issue(store, "历史浏览异常", "按用户反馈整理：只发截图也可以。") == first
    assert len(issues) == 1
    assert store.list() == []


@pytest.mark.parametrize("state,author,tree,parent", [("closed", "trusted-bot[bot]", "tree", "source"), ("open", "other", "tree", "source"), ("open", "trusted-bot[bot]", "old-tree", "source"), ("open", "trusted-bot[bot]", "tree", "old-source")])
def test_recovered_pr_must_match_open_bot_candidate(tmp_path, state, author, tree, parent):
    store = Store(tmp_path / "q.sqlite")
    task = store.enqueue(1, "input", "policy", "source")
    branch = "fix/issue-1-input-source"
    pr = {"number": 12, "state": state, "merged_at": None, "user": {"login": author}, "base": {"ref": "main", "repo": {"full_name": "uukuguy/capstone"}}, "head": {"ref": branch, "sha": "head", "repo": {"full_name": "uukuguy/capstone"}}}
    def api(method, path, data=None):
        if path == "app": return {"id": 123, "slug": "trusted-bot"}
        if path == "app/installations/123": return {"id": 123, "app_id": 123, "app_slug": "trusted-bot"}
        if path.endswith("access_tokens"): return {"token": "fake"}
        if path == "installation/repositories?per_page=100": return {"repositories": [{"full_name": "uukuguy/capstone"}]}
        if "/pulls?" in path: return [pr]
        if path.endswith("/git/blobs"): return {"sha": "blob"}
        if path.endswith("/git/trees"): return {"sha": "tree"}
        if path.endswith("/git/commits/source"): return {"tree": {"sha": "base-tree"}}
        if path.endswith("/git/commits/head"): return {"tree": {"sha": tree}, "parents": [{"sha": parent}]}
        if "/git/matching-refs/" in path: return [{"ref": "refs/heads/" + branch, "object": {"sha": "head"}}]
        raise AssertionError((method, path))
    github = GitHub(Policy(write_enabled=True, publisher_login="trusted-bot[bot]", publisher_app_id=123, publisher_installation_id=123), api=api, publisher_api=api)
    with pytest.raises(ValueError, match="candidate|pull request"):
        github.publish_candidate(store, task, branch, "source", {"packages/capstone-app/app.py": "fixed\n"}, "修复行为", "中文说明")


def test_existing_acceptance_tag_formats_are_recognized_without_inventing_verification():
    sha = "a" * 40
    for message, expected in (("stage: demo\nsource: " + sha + "\nverification: runs/demo/report.json", "legacy-text"), (json.dumps({"stage": "cloud-dev", "source_commit": sha, "deployments": ["d"], "verification_report": "runs/dev/report.json", "report_commit": sha}), "legacy-json")):
        name = "demo-20261010-1231-aaaaaaa" if expected == "legacy-text" else "cloud-dev-20261008-1941-aaaaaaa"
        def api(method, path, data=None):
            return {"object": {"type": "tag", "sha": "tag-object"}} if "/git/ref/" in path else {"object": {"type": "commit", "sha": sha}, "message": message}
        result = GitHub(Policy(), api=api).acceptance_tag(name)
        assert result["format"] == expected
        assert result["source_sha"] == sha
