#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any


class ConfigurationError(ValueError):
    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Git repository root to inspect.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(
            "configs/runtime/application-instantiation-protected-paths.json"
        ),
        help=(
            "Active C.1 protected-path policy at "
            "configs/runtime/application-instantiation-protected-paths.json."
        ),
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    config_path = args.config
    if not config_path.is_absolute():
        config_path = root / config_path

    try:
        protected = load_configuration(config_path)
        violations = check_protected_paths(root, protected)
    except ConfigurationError as exc:
        print(f"protected-paths configuration error: {exc}", file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError) as exc:
        print(f"protected-paths configuration error: {exc}", file=sys.stderr)
        return 2

    if violations:
        for violation in violations:
            print(violation, file=sys.stderr)
        return 1
    print("protected-paths: ok")
    return 0


def load_configuration(path: Path) -> dict[str, str]:
    document: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ConfigurationError("root document must be an object")
    paths = document.get("protected_paths")
    digests = document.get("protected_path_digests")
    if not isinstance(paths, list) or not all(
        isinstance(path, str) for path in paths
    ):
        raise ConfigurationError("protected_paths must be a string array")
    if not isinstance(digests, dict):
        raise ConfigurationError("protected_path_digests must be an object")
    if len(paths) != len(set(paths)):
        raise ConfigurationError("protected_paths must not contain duplicates")
    if set(paths) != set(digests):
        raise ConfigurationError(
            "protected_paths and protected_path_digests must have identical keys"
        )

    validated: dict[str, str] = {}
    for path in paths:
        pure_path = PurePosixPath(path)
        if pure_path.is_absolute() or ".." in pure_path.parts or path in ("", "."):
            raise ConfigurationError(f"unsafe protected path: {path}")
        digest = digests[path]
        if not isinstance(digest, str) or not re.fullmatch(
            r"[a-f0-9]{40}(?:[a-f0-9]{24})?", digest
        ):
            raise ConfigurationError(f"invalid tree digest for {path}")
        validated[path] = digest
    return validated


def check_protected_paths(
    root: Path,
    protected: dict[str, str],
) -> list[str]:
    assert_git_repository(root)
    paths = list(protected)
    changed_paths = working_tree_changes(root, paths)
    if changed_paths:
        return [
            f"protected path has working-tree changes: {path}"
            for path in changed_paths
        ]

    violations: list[str] = []
    for path, expected in protected.items():
        completed = git(root, "rev-parse", f"HEAD:{path}", check=False)
        actual = completed.stdout.strip() if completed.returncode == 0 else "<missing>"
        if actual != expected:
            violations.append(
                f"protected path tree mismatch: {path} expected {expected}, got {actual}"
            )
    return violations


def assert_git_repository(root: Path) -> None:
    completed = git(root, "rev-parse", "--show-toplevel", check=False)
    if completed.returncode != 0 or Path(completed.stdout.strip()).resolve() != root:
        raise ConfigurationError(f"root is not a Git repository: {root}")


def working_tree_changes(root: Path, paths: list[str]) -> list[str]:
    commands = (
        ("diff", "--name-only", "--"),
        ("diff", "--cached", "--name-only", "--"),
        ("ls-files", "--others", "--exclude-standard", "--"),
    )
    changed: set[str] = set()
    for prefix in commands:
        output = git(root, *prefix, *paths).stdout
        changed.update(line for line in output.splitlines() if line)
    return sorted(changed)


def git(
    root: Path,
    *arguments: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=check,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        raise ConfigurationError(
            exc.stderr.strip() or f"git {' '.join(arguments)} failed"
        ) from exc


if __name__ == "__main__":
    raise SystemExit(main())
