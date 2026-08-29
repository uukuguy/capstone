from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "tools/check_protected_paths.py"


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


def run_checker(repository: Path, config: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(CHECKER),
            "--root",
            str(repository),
            "--config",
            str(config),
        ],
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
