from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "tools/check_protected_paths.py"
ACTIVE_POLICY = (
    ROOT / "configs/runtime/application-instantiation-protected-paths.json"
)
EXPECTED_C1_PROTECTED_PATHS = {
    "configs/capabilities/pandapower-3.4.0-static-analysis.json",
    "packages/grid-simulator",
    "packages/inventory-domain-pack",
    "packages/inventory-reference-service",
    "validation/questions/task.md.txt",
    "validation/questions/test.md.txt",
}
MUTABLE_C1_PATHS = {
    "packages/capability-agent-kernel",
    "packages/pi-capability-tools",
    "packages/trajectory-workbench",
    "packages/grid-agent",
    "packages/pandapower-domain-pack",
}


def test_active_c1_policy_protects_exactly_immutable_inputs_and_truth() -> None:
    document = json.loads(ACTIVE_POLICY.read_text(encoding="utf-8"))

    protected_paths = set(document["protected_paths"])
    assert protected_paths == EXPECTED_C1_PROTECTED_PATHS
    assert set(document["protected_path_digests"]) == EXPECTED_C1_PROTECTED_PATHS
    assert protected_paths.isdisjoint(MUTABLE_C1_PATHS)
    for path in protected_paths:
        assert document["protected_path_digests"][path] == git(
            ROOT, "rev-parse", f"HEAD:{path}"
        ).stdout.strip()


def test_repository_checker_defaults_to_active_c1_policy() -> None:
    result = run_checker(ROOT)

    assert result.returncode == 0
    assert result.stdout == "protected-paths: ok\n"
    assert result.stderr == ""


def test_checker_help_identifies_active_c1_policy() -> None:
    result = subprocess.run(
        [sys.executable, str(CHECKER), "--help"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "Active C.1 protected-path policy" in result.stdout
    assert (
        "configs/runtime/application-instantiation-protected-paths.json"
        in "".join(line.strip() for line in result.stdout.splitlines())
    )


def test_make_protected_paths_gate_explicitly_uses_active_c1_policy() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert (
        "check-protected-paths:\n"
        "\tpython3 tools/check_protected_paths.py \\\n"
        "\t\t--config configs/runtime/application-instantiation-protected-paths.json"
        in makefile
    )


def test_matching_clean_protected_tree_passes(tmp_path: Path) -> None:
    repository, config = make_repository(tmp_path)

    result = run_checker(repository, config)

    assert result.returncode == 0
    assert result.stdout == "protected-paths: ok\n"
    assert result.stderr == ""


def test_changed_committed_protected_tree_fails(tmp_path: Path) -> None:
    repository, config = make_repository(tmp_path)
    protected_file = repository / "packages/kernel/value.txt"
    protected_file.write_text("changed\n", encoding="utf-8")
    git(repository, "add", protected_file.relative_to(repository).as_posix())
    git(repository, "commit", "-m", "change protected path")

    result = run_checker(repository, config)

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.startswith(
        "protected path tree mismatch: packages/kernel expected "
    )


def test_dirty_or_untracked_protected_path_fails(tmp_path: Path) -> None:
    repository, config = make_repository(tmp_path)
    (repository / "packages/kernel/value.txt").write_text(
        "dirty\n", encoding="utf-8"
    )
    (repository / "packages/kernel/untracked.txt").write_text(
        "untracked\n", encoding="utf-8"
    )

    result = run_checker(repository, config)

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.splitlines() == [
        "protected path has working-tree changes: packages/kernel/untracked.txt",
        "protected path has working-tree changes: packages/kernel/value.txt",
    ]


def test_missing_or_malformed_config_fails_closed(tmp_path: Path) -> None:
    repository, config = make_repository(tmp_path)
    config.write_text('{"protected_paths": ["packages/kernel"]}\n', encoding="utf-8")

    result = run_checker(repository, config)

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == (
        "protected-paths configuration error: protected_path_digests must be an object\n"
    )


def make_repository(tmp_path: Path) -> tuple[Path, Path]:
    repository = tmp_path / "repository"
    protected = repository / "packages/kernel"
    protected.mkdir(parents=True)
    (protected / "value.txt").write_text("baseline\n", encoding="utf-8")
    git(repository, "init", "-q")
    git(repository, "config", "user.email", "test@example.invalid")
    git(repository, "config", "user.name", "Test")
    git(repository, "add", ".")
    git(repository, "commit", "-q", "-m", "baseline")
    digest = git(repository, "rev-parse", "HEAD:packages/kernel").stdout.strip()
    config = repository / "config.json"
    config.write_text(
        json.dumps(
            {
                "protected_paths": ["packages/kernel"],
                "protected_path_digests": {"packages/kernel": digest},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return repository, config


def run_checker(
    repository: Path,
    config: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(CHECKER),
        "--root",
        str(repository),
    ]
    if config is not None:
        command.extend(["--config", str(config)])
    return subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=True,
    )


def git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        text=True,
        capture_output=True,
    )
