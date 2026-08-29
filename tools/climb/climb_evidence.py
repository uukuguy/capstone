from __future__ import annotations

import json
import hashlib
import hmac
import os
import secrets
import stat
import subprocess
from pathlib import Path
from typing import TypeVar, cast


ROOT = Path(__file__).resolve().parents[2]
JsonObject = dict[str, object]
T = TypeVar("T")

CANONICAL_RELEASE_INCLUDE = (
    "AGENTS.md",
    "CLAUDE.md",
    "Makefile",
    "README.md",
    "README.zh-CN.md",
    "packages",
    "tools",
    "validation",
    "configs",
    "schemas",
    "skills",
    "docs/RUNBOOK.md",
    "docs/architecture",
    "docs/status/climb/config.yaml",
)
CANONICAL_RELEASE_EXCLUDE = (".superpowers",)
CLOSURE_GATE_ORDER = (
    "kernel_independence",
    "domain_ownership",
    "pi_tool_generalization",
    "application_thinness",
    "distribution_integrity",
    "doctor",
    "test",
    "test-e2e",
    "product_compatibility",
)
CANONICAL_GATE_COMMANDS: dict[str, tuple[str, ...]] = {
    "kernel_independence": (
        "uv",
        "run",
        "--project",
        "packages/grid-agent",
        "pytest",
        "packages/capability-agent-kernel/tests",
        "-q",
    ),
    "domain_ownership": ("make", "test-domain-package"),
    "pi_tool_generalization": (
        "npm",
        "test",
        "--prefix",
        "packages/pi-capability-tools",
    ),
    "application_thinness": ("make", "check-package-boundaries"),
    "distribution_integrity": ("make", "test-packages"),
    "doctor": ("make", "doctor"),
    "test": ("make", "test"),
    "test-e2e": ("make", "test-e2e"),
    "product_compatibility": ("make", "validate"),
}
CANONICAL_SCORE_WEIGHTS = {
    "kernel_independence": 25.0,
    "domain_ownership": 20.0,
    "pi_tool_generalization": 15.0,
    "application_thinness": 10.0,
    "distribution_integrity": 10.0,
    "product_compatibility": 20.0,
}
INVENTORY_RELEASE_POLICY_ID = "workstream-c-inventory-v1"
INVENTORY_CLOSURE_GATE_ORDER = (
    "reference_authority",
    "domain_pack_spi",
    "generic_pi_transport",
    "authority_lineage",
    "distribution_integrity",
    "doctor",
    "test",
    "test-e2e",
    "product_compatibility",
)
INVENTORY_GATE_COMMANDS: dict[str, tuple[str, ...]] = {
    "reference_authority": ("make", "test-inventory-service"),
    "domain_pack_spi": ("make", "test-inventory-domain"),
    "generic_pi_transport": ("make", "test-inventory-pi"),
    "authority_lineage": (
        "uv",
        "run",
        "--project",
        "packages/inventory-domain-pack",
        "pytest",
        "packages/inventory-domain-pack/tests/test_authority.py",
        "-q",
    ),
    "distribution_integrity": ("make", "test-packages"),
    "doctor": ("make", "doctor"),
    "test": ("make", "test"),
    "test-e2e": ("make", "test-e2e"),
    "product_compatibility": ("make", "validate"),
}
INVENTORY_SCORE_WEIGHTS = {
    "reference_authority": 25.0,
    "domain_pack_spi": 20.0,
    "generic_pi_transport": 15.0,
    "authority_lineage": 20.0,
    "distribution_integrity": 10.0,
    "product_compatibility": 10.0,
}


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


def policy_sha256(config: JsonObject) -> str:
    """Digest the complete committed scoring and command policy document."""

    return sha256_bytes(canonical_json_bytes(config))


def release_gate_order(config: JsonObject) -> tuple[str, ...]:
    policy_id = config.get("release_policy_id")
    if policy_id is None:
        return CLOSURE_GATE_ORDER
    if policy_id == INVENTORY_RELEASE_POLICY_ID:
        return INVENTORY_CLOSURE_GATE_ORDER
    raise ValueError(f"unknown release policy id: {policy_id}")


def release_gate_commands(config: JsonObject) -> dict[str, tuple[str, ...]]:
    return (
        INVENTORY_GATE_COMMANDS
        if config.get("release_policy_id") == INVENTORY_RELEASE_POLICY_ID
        else CANONICAL_GATE_COMMANDS
    )


def release_score_weights(config: JsonObject) -> dict[str, float]:
    return (
        INVENTORY_SCORE_WEIGHTS
        if config.get("release_policy_id") == INVENTORY_RELEASE_POLICY_ID
        else CANONICAL_SCORE_WEIGHTS
    )


def validate_release_policy(config: JsonObject) -> None:
    """Reject a weakened versioned release policy before any gate runs."""

    try:
        gate_order = release_gate_order(config)
        gate_commands = release_gate_commands(config)
        score_weights = release_score_weights(config)
        closure = as_object(config.get("closure"), "closure")
        if closure != {
            "gate_order": list(gate_order),
            "mode": "rerun-all-gates-v1",
        }:
            raise ValueError("closure mode or gate order changed")
        release_source = as_object(config.get("release_source"), "release_source")
        if release_source != {
            "enforce_clean": True,
            "include_pathspecs": list(CANONICAL_RELEASE_INCLUDE),
            "exclude_pathspecs": list(CANONICAL_RELEASE_EXCLUDE),
        }:
            raise ValueError("release-source pathspec policy changed")
        weights = as_object(config.get("score_weights"), "score_weights")
        if set(weights) != set(score_weights) or any(
            float(str(weights[key])) != expected
            for key, expected in score_weights.items()
        ):
            raise ValueError("score weights changed")
        if config.get("subscores") != list(score_weights):
            raise ValueError("score key order changed")
        score_gates = as_object(config.get("score_gates"), "score_gates")
        receipt_gates = as_object(config.get("receipt_gates"), "receipt_gates")
        for key, expected in gate_commands.items():
            section = receipt_gates if key in {"doctor", "test", "test-e2e"} else score_gates
            gate = as_object(section.get(key), f"gate {key}")
            if gate.get("command") != list(expected):
                raise ValueError(f"gate command changed: {key}")
        for key in tuple(score_weights)[:-1]:
            gate = as_object(score_gates.get(key), f"gate {key}")
            if gate.get("receipt_required") is not True:
                raise ValueError(f"receipt gate policy changed: {key}")
        product = as_object(
            score_gates.get("product_compatibility"),
            "gate product_compatibility",
        )
        if product.get("prerequisite_receipts") != ["doctor", "test", "test-e2e"]:
            raise ValueError("product prerequisite graph changed")
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"release policy is not canonical: {exc}") from exc


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
    if config.get("closure") is not None:
        validate_release_policy(config)
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


def release_source_is_clean(config: JsonObject, root: Path = ROOT) -> bool:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            *release_source_pathspecs(config),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            completed.stderr.decode("utf-8", errors="replace").strip()
            or "could not inspect release source status"
        )
    return completed.stdout == b""


def require_clean_release_source(config: JsonObject, root: Path = ROOT) -> None:
    release_source = optional_object(config.get("release_source"), "release_source")
    if bool(release_source.get("enforce_clean")) and not release_source_is_clean(config, root):
        raise ValueError("release-source pathspec is dirty")


def release_source_tree_sha256(
    config: JsonObject,
    revision: str,
    root: Path = ROOT,
) -> str:
    if config.get("closure") is not None:
        validate_release_policy(config)
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
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "ls-tree",
            "-r",
            "-z",
            revision,
            "--",
            *include,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            completed.stderr.decode("utf-8", errors="replace").strip()
            or "could not digest release source tree"
        )
    records = []
    for record in completed.stdout.split(b"\0"):
        if not record:
            continue
        _metadata, separator, raw_path = record.partition(b"\t")
        if not separator:
            raise RuntimeError("could not parse release source tree")
        path = raw_path.decode("utf-8", errors="surrogateescape")
        if any(path == item.rstrip("/") or path.startswith(f"{item.rstrip('/')}/") for item in exclude):
            continue
        records.append(record)
    return hashlib.sha256(b"\0".join(records) + (b"\0" if records else b"")).hexdigest()


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


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def receipt_payload(receipt: JsonObject) -> JsonObject:
    return {
        key: value
        for key, value in receipt.items()
        if key not in {"attestation", "receipt_digest"}
    }


def receipt_digest(receipt: JsonObject) -> str:
    return sha256_bytes(canonical_json_bytes(receipt_payload(receipt)))


def attestation_key_path(root: Path = ROOT) -> Path:
    return root / ".grid-agent" / "climb-receipt-hmac.key"


def load_attestation_key(*, root: Path = ROOT, create: bool = False) -> bytes:
    internal = root / ".grid-agent"
    if create:
        internal.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        internal_status = internal.lstat()
    except FileNotFoundError as exc:
        raise ValueError("controller attestation key is unavailable") from exc
    if not stat.S_ISDIR(internal_status.st_mode) or stat.S_ISLNK(internal_status.st_mode):
        raise ValueError("controller attestation directory is unsafe")
    key_path = attestation_key_path(root)
    if create and not key_path.exists():
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
        try:
            descriptor = os.open(key_path, flags, 0o600)
        except FileExistsError:
            pass
        else:
            try:
                key = secrets.token_bytes(32)
                if os.write(descriptor, key) != len(key):
                    raise OSError("short attestation key write")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    try:
        status = key_path.lstat()
    except FileNotFoundError as exc:
        raise ValueError("controller attestation key is unavailable") from exc
    if (
        not stat.S_ISREG(status.st_mode)
        or stat.S_ISLNK(status.st_mode)
        or stat.S_IMODE(status.st_mode) != 0o600
        or status.st_uid != os.getuid()
    ):
        raise ValueError("controller attestation key must be owned mode-0600 regular data")
    descriptor = os.open(key_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        key = _read_descriptor(descriptor)
    finally:
        os.close(descriptor)
    if len(key) != 32:
        raise ValueError("controller attestation key must contain exactly 32 bytes")
    return key


def attestation_key_id(key: bytes) -> str:
    return sha256_bytes(key)[:24]


def sign_receipt(receipt: JsonObject, key: bytes) -> JsonObject:
    digest = receipt_digest(receipt)
    signature = hmac.new(key, digest.encode("ascii"), hashlib.sha256).hexdigest()
    return {
        **receipt,
        "receipt_digest": digest,
        "attestation": {
            "algorithm": "hmac-sha256",
            "key_id": attestation_key_id(key),
            "purpose": "same-user-integrity-only",
            "signature": signature,
        },
    }


def verify_receipt_attestation(receipt: JsonObject, key: bytes) -> bool:
    attestation = receipt.get("attestation")
    if not isinstance(attestation, dict):
        return False
    digest = receipt_digest(receipt)
    expected_signature = hmac.new(
        key,
        digest.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return (
        receipt.get("receipt_digest") == digest
        and attestation.get("algorithm") == "hmac-sha256"
        and attestation.get("key_id") == attestation_key_id(key)
        and attestation.get("purpose") == "same-user-integrity-only"
        and isinstance(attestation.get("signature"), str)
        and hmac.compare_digest(str(attestation["signature"]), expected_signature)
    )


def secure_artifact_bytes(path: Path, *, artifact: Path) -> bytes:
    artifact_absolute = artifact.absolute()
    path_absolute = path.absolute()
    try:
        relative = path_absolute.relative_to(artifact_absolute)
    except ValueError as exc:
        raise ValueError("artifact path escapes artifact_dir") from exc
    if not relative.parts:
        raise ValueError("artifact path must name a regular file")
    _reject_symlink_chain(artifact_absolute)
    root_descriptor = os.open(
        artifact_absolute,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    descriptors: list[int] = []
    bindings: list[tuple[int, str, int, bool]] = []
    parent = root_descriptor
    try:
        for part in relative.parts[:-1]:
            descriptor = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent,
            )
            descriptors.append(descriptor)
            bindings.append((parent, part, descriptor, True))
            parent = descriptor
        leaf = os.open(
            relative.parts[-1],
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent,
        )
        descriptors.append(leaf)
        bindings.append((parent, relative.parts[-1], leaf, False))
        before = os.fstat(leaf)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("artifact leaf is not a regular file")
        content = _read_descriptor(leaf)
        after = os.fstat(leaf)
        for binding_parent, name, descriptor, directory in bindings:
            named = os.stat(name, dir_fd=binding_parent, follow_symlinks=False)
            opened = os.fstat(descriptor)
            expected_kind = stat.S_ISDIR(named.st_mode) if directory else stat.S_ISREG(named.st_mode)
            if (
                not expected_kind
                or named.st_dev != opened.st_dev
                or named.st_ino != opened.st_ino
            ):
                raise ValueError("artifact named binding changed")
        if _stat_identity(before) != _stat_identity(after):
            raise ValueError("artifact changed while it was read")
        return content
    except OSError as exc:
        raise ValueError(f"artifact path is unsafe: {exc}") from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        os.close(root_descriptor)


def secure_artifact_makedirs(path: Path, *, artifact: Path) -> None:
    artifact_absolute = artifact.absolute()
    path_absolute = path.absolute()
    try:
        relative = path_absolute.relative_to(artifact_absolute)
    except ValueError as exc:
        raise ValueError("artifact directory escapes artifact_dir") from exc
    artifact_absolute.mkdir(parents=True, exist_ok=True)
    _reject_symlink_chain(artifact_absolute)
    parent = os.open(
        artifact_absolute,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        for part in relative.parts:
            try:
                os.mkdir(part, 0o700, dir_fd=parent)
            except FileExistsError:
                pass
            child = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent,
            )
            os.close(parent)
            parent = child
    except OSError as exc:
        raise ValueError(f"artifact directory path is unsafe: {exc}") from exc
    finally:
        os.close(parent)


def _reject_symlink_chain(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        status = current.lstat()
        if stat.S_ISLNK(status.st_mode):
            raise ValueError(f"artifact parent chain contains symlink: {current}")


def _read_descriptor(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 64 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _stat_identity(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mode,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )
