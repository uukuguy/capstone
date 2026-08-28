from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import TypeVar, cast


ROOT = Path(__file__).resolve().parents[2]
JsonObject = dict[str, object]
T = TypeVar("T")


def as_object(value: object, name: str) -> JsonObject:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return cast(JsonObject, value)


def optional_object(value: object, name: str) -> JsonObject:
    if value is None:
        return {}
    return as_object(value, name)


def as_list(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a JSON array")
    return value


def as_string_list(value: object, name: str) -> list[str]:
    return [str(item) for item in as_list(value, name)]


def load_json_object(path: Path) -> JsonObject:
    return as_object(json.loads(path.read_text(encoding="utf-8")), str(path))


def state_dir(root: Path = ROOT) -> Path:
    raw = os.environ.get("CLIMB_STATE_DIR")
    if raw:
        path = Path(raw)
        return path if path.is_absolute() else root / path
    return root / "docs/status/climb"


def artifact_dir(config: JsonObject, root: Path = ROOT) -> Path:
    raw = os.environ.get("CLIMB_ARTIFACT_DIR") or str(config.get("artifact_dir", "runs/climb"))
    path = Path(raw)
    return path if path.is_absolute() else root / path


def stable_path(path: Path, *, root: Path = ROOT, state: Path | None = None, artifact: Path | None = None) -> str:
    resolved = path.resolve()
    state_base = state or state_dir(root)
    artifact_base = artifact or artifact_dir(load_json_object(state_base / "config.yaml"), root)
    for base in (root.resolve(), artifact_base.resolve(), state_base.resolve()):
        try:
            return resolved.relative_to(base).as_posix()
        except ValueError:
            continue
    return path.name


def release_source_pathspecs(config: JsonObject) -> list[str]:
    release_source = optional_object(config.get("release_source"), "release_source")
    include = as_string_list(
        release_source.get(
            "include_pathspecs",
            ["Makefile", "packages", "tools", "validation", "configs", "schemas", "skills"],
        ),
        "release_source.include_pathspecs",
    )
    exclude = as_string_list(
        release_source.get("exclude_pathspecs", ["docs/status", ".superpowers"]),
        "release_source.exclude_pathspecs",
    )
    if not include:
        raise ValueError("release_source.include_pathspecs must not be empty")
    return [*include, *[f":(exclude){item}" for item in exclude]]


def source_revision(config: JsonObject, root: Path = ROOT) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "log", "-1", "--format=%H", "--", *release_source_pathspecs(config)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "could not resolve release source revision")
    revision = completed.stdout.strip()
    if not revision:
        raise RuntimeError("could not resolve release source revision")
    return revision


def receipt_path_for(config: JsonObject, gate_key: str, revision: str, *, root: Path = ROOT) -> Path:
    return artifact_dir(config, root) / "gate-receipts" / revision / f"{gate_key}.json"


def receipt_output_path_for(config: JsonObject, gate_key: str, revision: str, *, root: Path = ROOT) -> Path:
    return artifact_dir(config, root) / "gate-receipts" / revision / f"{gate_key}.output.txt"


def contained_artifact_path(raw: object, *, root: Path = ROOT, artifact: Path) -> Path:
    if not isinstance(raw, str) or not raw:
        raise ValueError("artifact path must be a non-empty string")
    path = Path(raw)
    if path.is_absolute():
        candidate = path
    else:
        root_candidate = root / path
        candidate = root_candidate if root_candidate.exists() else artifact / path
    resolved = candidate.resolve()
    artifact_resolved = artifact.resolve()
    try:
        resolved.relative_to(artifact_resolved)
    except ValueError as exc:
        raise ValueError(f"artifact path escapes artifact_dir: {raw}") from exc
    if candidate.is_symlink():
        raise ValueError(f"artifact path is a symlink: {raw}")
    return resolved
