import dataclasses
import json
import os
from pathlib import Path
import subprocess

import pytest

from tools.issue_automation.cli import main, load_policy
from tools.issue_automation.policy import Policy
from tools.issue_automation.repair import DockerSandbox


def test_doctor_uses_trusted_main_config_and_disabled_model(tmp_path, capsys):
    subprocess.run(["git", "init", "-b", "main", str(tmp_path)], check=True, capture_output=True)
    config = tmp_path / "configs/development/issue-automation.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps(dataclasses.asdict(Policy())))
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "policy"], check=True, capture_output=True)
    config.write_text('{"model_enabled":true}')
    assert main(["doctor", "--root", str(tmp_path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "manual"
    assert output["model_enabled"] is False
    assert "No prepared sandbox image" in output["blockers"]


def test_private_override_requires_ignored_owner_only_file(tmp_path):
    from tools.issue_automation.cli import operator_override
    state = tmp_path / ".capstone-agent/issue-automation"
    state.mkdir(parents=True)
    override = state / "operator.json"
    override.write_text('{"write_enabled":true}')
    override.chmod(0o644)
    with pytest.raises(ValueError):
        operator_override(tmp_path, Policy())


@pytest.mark.parametrize("profile,accepted,rejected", [
    ("app", "packages/capstone-app/src/app.ts", "packages/capstone-agent/src/app.py"),
    ("backend", "packages/capstone-agent/src/app.py", "packages/capstone-app/src/app.ts"),
    ("app-and-backend", "packages/capstone-agent/tests/test_app.py", "packages/other/app.py"),
])
def test_profile_selection_rejects_candidate_edits_outside_checked_scope(tmp_path, profile, accepted, rejected):
    from tools.issue_automation.cli import operator_override
    from tools.issue_automation.repair import Repair, Source
    subprocess.run(["git", "init", "-b", "main", str(tmp_path)], check=True, capture_output=True)
    (tmp_path / ".gitignore").write_text(".capstone-agent/\n")
    for path in (accepted, rejected):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("// trusted source\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "base"], check=True, capture_output=True)
    settings = tmp_path / ".capstone-agent/issue-automation/operator.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"check_profile": profile}))
    settings.chmod(0o600)
    trusted = dataclasses.replace(Policy(), edit_prefixes=("packages/capstone-app/src/", "packages/capstone-agent/", "packages/other/"))
    policy = operator_override(tmp_path, trusted)
    assert any(accepted.startswith(prefix) for prefix in policy.edit_prefixes)
    assert "packages/other/" not in policy.edit_prefixes
    if profile != "backend":
        assert "packages/capstone-app/src/" in policy.edit_prefixes
        assert "packages/capstone-app/" not in policy.edit_prefixes
    repair = Repair(policy, Source(tmp_path), None, None, tmp_path / "state")
    repair.prepare("task", [rejected])
    with pytest.raises(ValueError, match="permitted source scope"):
        repair.validate_manual("task", {"summary": "拒绝未检查范围的候选", "reproduction_check": 0, "files": [{"path": rejected, "content": "// candidate\n"}]})


def test_main_profile_scope_is_applied_without_operator_override(tmp_path):
    from tools.issue_automation.cli import operator_override
    trusted = dataclasses.replace(Policy(), check_profile="backend", edit_prefixes=("packages/",))
    policy = operator_override(tmp_path, trusted)
    assert policy.edit_prefixes == ("packages/capstone-agent/src/", "packages/capstone-agent/tests/")


@pytest.mark.skipif(not os.environ.get("ISSUE_AUTOMATION_TEST_IMAGE"), reason="Prepared Docker image not selected")
def test_real_docker_candidate_is_secret_free_and_offline(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "host-only-secret")
    script = tmp_path / "check.py"
    tmp_path.chmod(0o755)
    script.write_text("import os, socket\nassert 'OPENAI_API_KEY' not in os.environ\nassert not os.path.exists('/source/.git')\nassert not os.path.exists('/source/.grid-agent')\ns = socket.socket()\ns.settimeout(0.2)\nassert s.connect_ex(('1.1.1.1', 443)) != 0\nprint('candidate passed')\n")
    policy = dataclasses.replace(Policy(), sandbox_image=os.environ["ISSUE_AUTOMATION_TEST_IMAGE"])
    result = DockerSandbox(policy).run(tmp_path, (("/usr/local/bin/python", "check.py"),), 30)
    assert result["passed"] is True


@pytest.mark.skipif(not os.environ.get("ISSUE_AUTOMATION_TEST_IMAGE"), reason="Prepared Docker image not selected")
def test_real_docker_baseline_regression_and_repair_receipt(tmp_path):
    from tools.issue_automation.repair import Source, Repair
    subprocess.run(["git", "init", "-b", "main", str(tmp_path)], check=True, capture_output=True)
    file = tmp_path / "packages/capstone-app/app.py"
    file.parent.mkdir(parents=True)
    file.write_text("value = 'broken'\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "base"], check=True, capture_output=True)
    policy = dataclasses.replace(Policy(), sandbox_image=os.environ["ISSUE_AUTOMATION_TEST_IMAGE"], checks=(("/usr/local/bin/python", "packages/capstone-app/tests/test_value.py"),))
    repair = Repair(policy, Source(tmp_path), None, DockerSandbox(policy), tmp_path / "state")
    repair.prepare("task", ["packages/capstone-app/app.py", "packages/capstone-app/tests/test_value.py"])
    result = repair.validate_manual("task", {"summary": "修复基础行为并添加回归检查", "reproduction_check": 0, "files": [{"path": "packages/capstone-app/app.py", "content": "value = 'fixed'\n"}, {"path": "packages/capstone-app/tests/test_value.py", "content": "from pathlib import Path\nnamespace = {}\nexec(Path('packages/capstone-app/app.py').read_text(), namespace)\nassert namespace['value'] == 'fixed'\n"}]})
    assert result["baseline"]["passed"] is False
    assert result["validation"]["passed"] is True
