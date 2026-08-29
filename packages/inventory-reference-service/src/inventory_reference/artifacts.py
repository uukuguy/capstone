from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Literal


ArtifactKind = Literal["revision", "context", "result", "evidence"]
_DIRECTORIES = {
    "revision": "revisions",
    "context": "contexts",
    "result": "results",
    "evidence": "facts",
}
_REFERENCE_PATTERN = re.compile(
    r"^inventory-(revision|context|result|evidence):sha256:([a-f0-9]{64})$"
)


def canonical_json_bytes(value: Mapping[str, object]) -> bytes:
    return json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def content_reference(kind: ArtifactKind, document: Mapping[str, object]) -> str:
    digest = hashlib.sha256(canonical_json_bytes(document)).hexdigest()
    return f"inventory-{kind}:sha256:{digest}"


def persist_document(
    workspace: Path,
    kind: ArtifactKind,
    document: Mapping[str, object],
) -> tuple[str, Path]:
    reference = content_reference(kind, document)
    digest = reference.rsplit(":", 1)[1]
    root = Path(workspace)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    target_dir = root / "evidence" / _DIRECTORIES[kind]
    target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root / "evidence", 0o700)
    os.chmod(target_dir, 0o700)
    path = target_dir / f"{digest}.json"
    payload = canonical_json_bytes(document) + b"\n"
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
        )
    except FileExistsError:
        if path.read_bytes() != payload:
            raise RuntimeError(f"inventory artifact collision: {reference}")
        return reference, path
    try:
        if os.write(descriptor, payload) != len(payload):
            raise OSError(f"short write for inventory artifact: {reference}")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return reference, path


def load_document(
    workspace: Path,
    reference: str,
    expected_kind: ArtifactKind,
) -> dict[str, object]:
    matched = _REFERENCE_PATTERN.fullmatch(reference)
    if matched is None or matched.group(1) != expected_kind:
        raise ValueError(f"invalid inventory {expected_kind} reference")
    digest = matched.group(2)
    path = Path(workspace) / "evidence" / _DIRECTORIES[expected_kind] / f"{digest}.json"
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError(reference)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid inventory {expected_kind} document") from exc
    if not isinstance(value, dict) or content_reference(expected_kind, value) != reference:
        raise ValueError(f"inventory {expected_kind} digest mismatch")
    return value
