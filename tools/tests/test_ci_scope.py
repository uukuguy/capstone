"""Check that development shortcuts never hide product or release changes."""
from tools.ci_scope import classify, check_document_links
import pytest
from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def test_documentation_and_overview_changes():
    assert classify(["docs/status/PROJECT-OVERVIEW.html", "README.md"]) == "docs"
    assert classify(["tools/project_overview/template.html", "tools/render_project_overview.py"]) == "docs"


def test_governance_changes_require_gate_tests():
    assert classify([".github/workflows/verify.yml", "tools/ci_scope.py", "docs/RUNBOOK.md"]) == "governance"
    assert classify(["tools/tests/test_verification_targets.py"]) == "governance"
    assert classify(["tools/issue_automation/cli.py", "tools/tests/test_issue_automation_cli.py"]) == "governance"


def test_product_and_unknown_paths_fail_closed():
    for path in ["packages/capstone-agent/src/server.py", "Makefile", "uv.lock",
                 ".github/workflows/deploy.yml", "tools/unregistered_tool.py",
                 "README.md.py", "docs/../packages/model.py"]:
        assert classify(["docs/RUNBOOK.md", path]) == "product"
    assert classify([]) == "product"


def test_main_and_explicit_release_always_use_complete_gate():
    assert classify(["README.md"], target="main") == "release"
    assert classify(["README.md"], release=True) == "release"


def workflow_scope_script():
    workflow = (ROOT / ".github/workflows/verify.yml").read_text()
    script = workflow.split("        run: |\n", 1)[1].split("      - name: Install uv", 1)[0]
    return "\n".join(line.removeprefix("          ") for line in script.splitlines())


def test_workflow_classifier_failure_cannot_produce_green_gate(tmp_path):
    output = tmp_path / "output"
    result = subprocess.run(["bash", "-e", "-c", workflow_scope_script()], cwd=ROOT,
                            env={**os.environ, "BASE_SHA": "missing-revision",
                                 "HEAD_SHA": "HEAD", "TARGET_BRANCH": "dev",
                                 "RELEASE_CHECK": "false", "GITHUB_OUTPUT": str(output)},
                            capture_output=True)
    assert result.returncode != 0
    assert not output.exists()


def test_new_main_branch_event_still_requires_release(tmp_path):
    output = tmp_path / "output"
    result = subprocess.run(["bash", "-e", "-c", workflow_scope_script()], cwd=ROOT,
                            env={**os.environ, "BASE_SHA": "0" * 40, "HEAD_SHA": "HEAD",
                                 "TARGET_BRANCH": "main", "RELEASE_CHECK": "false",
                                 "GITHUB_OUTPUT": str(output)}, capture_output=True)
    assert result.returncode == 0
    assert output.read_text().strip() == "gate=release"


def test_document_links_check_targets_and_allow_deleted_documents(tmp_path):
    (tmp_path / "guide.md").write_text("[target](target.md#topic) [web](https://example.com/)")
    with pytest.raises(ValueError, match="target.md"):
        check_document_links(tmp_path, ["guide.md"])
    (tmp_path / "target.md").write_text("# Topic")
    check_document_links(tmp_path, ["guide.md", "deleted.md"])


@pytest.fixture
def delivery_repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("/runs/\n")
    (tmp_path / "docs/status").mkdir(parents=True)
    return tmp_path


@pytest.mark.parametrize("name", ["README.md", "bundle.tar.gz", "bundle.tar.gz.sha256"])
def test_missing_ignored_delivery_links_pass_in_fresh_checkout(delivery_repo, name):
    guide = delivery_repo / "docs/status/guide.md"
    guide.write_text(f"[delivery](../../runs/user-local-offline/release/{name})")
    check_document_links(delivery_repo, ["docs/status/guide.md"])


@pytest.mark.parametrize("target", [
    "../missing.md", "../../runs/other/README.md",
    "../../runs/user-local-offline/release/other.md",
    "../../runs/user-local-offline/release/file.json",
    "../../runs/user-local-offline/.private/README.md",
    "../../runs/user-local-offline/release/../README.md",
    "../../runs/user-local-offline/%72elease/README.md",
    "../../../outside/runs/user-local-offline/README.md",
])
def test_missing_non_delivery_links_still_fail(delivery_repo, target):
    (delivery_repo / "docs/status/guide.md").write_text(f"[bad]({target})")
    with pytest.raises(ValueError, match="Missing relative"):
        check_document_links(delivery_repo, ["docs/status/guide.md"])


def test_missing_delivery_requires_git_ignore(delivery_repo):
    (delivery_repo / ".gitignore").write_text("")
    (delivery_repo / "docs/status/guide.md").write_text(
        "[delivery](../../runs/user-local-offline/release/README.md)")
    with pytest.raises(ValueError, match="Missing relative"):
        check_document_links(delivery_repo, ["docs/status/guide.md"])


def test_delivery_symlink_is_not_an_existence_exception(delivery_repo):
    delivery = delivery_repo / "runs/user-local-offline"
    delivery.mkdir(parents=True)
    (delivery / "release").symlink_to(delivery_repo / "missing", target_is_directory=True)
    (delivery_repo / "docs/status/guide.md").write_text(
        "[delivery](../../runs/user-local-offline/release/README.md)")
    with pytest.raises(ValueError, match="Missing relative"):
        check_document_links(delivery_repo, ["docs/status/guide.md"])


@pytest.mark.parametrize("target", ["javascript:alert", "/runs/user-local-offline/README.md",
                                   "https://example.com/README.md", "//example.com/README.md"])
def test_external_and_absolute_links_never_receive_delivery_exception(delivery_repo, target):
    from tools.ci_scope import is_ignored_delivery_link
    assert not is_ignored_delivery_link(delivery_repo, delivery_repo / "docs/status/guide.md", target)


def test_git_ignore_failure_cannot_exempt_delivery(delivery_repo, monkeypatch):
    import tools.ci_scope as scope
    calls = []

    def failed_git(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 128)

    monkeypatch.setattr(scope.subprocess, "run", failed_git)
    guide = delivery_repo / "docs/status/guide.md"
    guide.write_text("[delivery](../../runs/user-local-offline/release/README.md)")
    with pytest.raises(ValueError, match="Missing relative"):
        scope.check_document_links(delivery_repo, ["docs/status/guide.md"])
    assert calls == [["git", "-C", str(delivery_repo.resolve()), "check-ignore", "-q", "--",
                      "runs/user-local-offline/release/README.md"]]
