import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.issue_automation import bootstrap


def app():
    return {"id": 42, "slug": "capstone-xiaoshi", "owner": {"login": "uukuguy"}, "permissions": dict(bootstrap.PERMISSIONS), "events": [], "pem": "-----BEGIN RSA PRIVATE KEY-----\nfixture-not-a-real-key\n-----END RSA PRIVATE KEY-----\n"}


def policy():
    from tools.issue_automation.policy import Policy
    return Policy(publisher_app_id=42, publisher_login="capstone-xiaoshi[bot]")


def test_manifest_has_no_automatic_or_oauth_access():
    value = bootstrap.manifest("http://127.0.0.1:18790", "nonce")
    assert value["public"] is False
    assert value["default_events"] == []
    assert value["hook_attributes"]["active"] is False
    assert value["request_oauth_on_install"] is False
    assert set(value["default_permissions"]) == {"contents", "issues", "pull_requests", "actions", "checks", "metadata"}
    assert value["setup_url"].endswith("/installed/nonce")


@pytest.mark.parametrize("field,value", [("owner", {"login": "other"}), ("slug", "bad<script>"), ("events", ["issue_comment"]), ("permissions", {**bootstrap.PERMISSIONS, "administration": "write"}), ("id", True), ("pem", "not-a-key")])
def test_registration_rejects_unexpected_identity_or_scope(field, value):
    document = app()
    document[field] = value
    with pytest.raises(ValueError):
        bootstrap.validate_app(document)


def test_store_preserves_runtime_profile_and_never_saves_oauth_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "load_policy", lambda *args: (policy(), None))
    directory = tmp_path / ".capstone-agent/issue-automation"
    directory.mkdir(parents=True)
    operator = directory / "operator.json"
    operator.write_text(json.dumps({"sandbox_image": "sha256:" + "a" * 64, "check_profile": "app-and-backend"}))
    value = {**app(), "client_secret": "fixture-only", "webhook_secret": "fixture-only"}
    assert bootstrap.store_app(tmp_path, value) == "capstone-xiaoshi"
    stored = json.loads(operator.read_text())
    assert stored["sandbox_image"] == "sha256:" + "a" * 64
    assert stored["write_enabled"] is False and stored["model_enabled"] is False
    assert stored["publisher_installation_id"] == 0
    assert "secret" not in operator.read_text()
    assert operator.stat().st_mode & 0o777 == 0o600
    key = directory / "app-private-key.pem"
    assert key.stat().st_mode & 0o777 == 0o600
    assert bootstrap.resume_app(tmp_path) == "capstone-xiaoshi"
    key.write_text("unrelated credential")
    with pytest.raises(ValueError, match="never overwritten"):
        bootstrap.store_app(tmp_path, value)


def test_operator_symlink_is_not_replaced(tmp_path):
    target = tmp_path / "target"
    target.write_text("preserved")
    link = tmp_path / "operator.json"
    link.symlink_to(target)
    with pytest.raises(ValueError):
        bootstrap.private_json(link, {"write_enabled": True})
    assert target.read_text() == "preserved"


@pytest.mark.parametrize("value", ["0", "-1", "1/other", "secret?code=1"])
def test_invalid_installation_id_does_not_call_network(tmp_path, value):
    with pytest.raises(ValueError):
        bootstrap.accept_installation(tmp_path, value)


@pytest.mark.parametrize("value", ["all", "selected"])
def test_installation_checks_scope_and_identity_before_enabling(tmp_path, monkeypatch, value):
    from dataclasses import replace
    directory = tmp_path / ".capstone-agent/issue-automation"
    directory.mkdir(parents=True)
    operator = directory / "operator.json"
    operator.write_text(json.dumps({"write_enabled": False, "model_enabled": False}))
    monkeypatch.setattr(bootstrap, "load_policy", lambda *args: (policy(), None))
    calls = []
    class Publisher:
        def __init__(self, selected, root):
            assert selected.publisher_installation_id == 123
        def _publisher_api(self, method, path, data=None):
            if method == "POST":
                assert data == {"permissions": {"metadata": "read"}}
                return {"token": "fixture-token"}
            if path.startswith("installation/repositories"):
                return {"total_count": 1, "repositories": [{"full_name": "uukuguy/capstone"}]}
            return {"account": {"login": "uukuguy"}, "repository_selection": value, "suspended_at": None}
        def identity(self):
            calls.append("verified")
            return "capstone-xiaoshi[bot]"
    monkeypatch.setattr(bootstrap, "GitHub", Publisher)
    if value == "all":
        with pytest.raises(ValueError, match="selected"):
            bootstrap.accept_installation(tmp_path, "123")
        assert not json.loads(operator.read_text())["write_enabled"]
        assert not calls
    else:
        assert bootstrap.accept_installation(tmp_path, "123") == "capstone-xiaoshi[bot]"
        assert calls == ["verified"]
        stored = json.loads(operator.read_text())
        assert stored["publisher_installation_id"] == 123 and stored["write_enabled"]
        assert not stored["model_enabled"]


def test_invalid_conversion_code_refused_before_request(monkeypatch):
    monkeypatch.setattr(bootstrap, "urlopen", lambda *args, **kwargs: pytest.fail("Unexpected network call"))
    with pytest.raises(ValueError):
        bootstrap.exchange("../../token")


def test_registration_recovers_after_operator_write_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "load_policy", lambda *args: (policy(), None))
    real_write = bootstrap.private_json
    def fail_operator(path, value):
        if Path(path).name == "operator.json":
            raise OSError("simulated full disk")
        return real_write(path, value)
    monkeypatch.setattr(bootstrap, "private_json", fail_operator)
    with pytest.raises(OSError):
        bootstrap.store_app(tmp_path, app())
    pending = tmp_path / ".capstone-agent/issue-automation/enrollment-pending.json"
    assert pending.stat().st_mode & 0o777 == 0o600
    assert "client_secret" not in pending.read_text()
    monkeypatch.setattr(bootstrap, "private_json", real_write)
    assert bootstrap.resume_app(tmp_path) == "capstone-xiaoshi"
    operator = json.loads((pending.parent / "operator.json").read_text())
    assert operator["publisher_app_id"] == 42 and not operator["write_enabled"]


def test_multi_repository_installation_is_not_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "load_policy", lambda *args: (policy(), None))
    class Publisher:
        def __init__(self, *args, **kwargs):
            pass
        def _publisher_api(self, method, path, data=None):
            if method == "POST":
                return {"token": "fixture-only"}
            if path.startswith("installation/repositories"):
                return {"total_count": 2, "repositories": [{"full_name": "uukuguy/capstone"}, {"full_name": "uukuguy/other"}]}
            return {"account": {"login": "uukuguy"}, "repository_selection": "selected"}
        def identity(self):
            pytest.fail("Write identity must not be enabled before installation scope passes")
    monkeypatch.setattr(bootstrap, "GitHub", Publisher)
    with pytest.raises(ValueError, match="outside capstone"):
        bootstrap.accept_installation(tmp_path, "123")
    assert not (tmp_path / ".capstone-agent/issue-automation/operator.json").exists()
