"""Verified lock-file models for the managed Pi runtime."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self


EXPECTED_SCHEMA_VERSION = 2
PATCH_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PiRuntimeLockError(ValueError):
    """Raised when a managed runtime lock is malformed or tampered with."""


@dataclass(frozen=True, slots=True)
class PiRuntimeIdentity:
    path: Path
    source: str
    package_version: str
    lock_sha256: str
    pi_ai_version: str = ""
    patches_sha256: str = ""
    commit: str | None = None
    version: str | None = None


@dataclass(frozen=True, slots=True)
class PiRuntimePatch:
    path: Path
    sha256: str


@dataclass(frozen=True, slots=True)
class PiCommand:
    argv: tuple[str, ...]
    identity: PiRuntimeIdentity

    @property
    def path(self) -> Path:
        return self.identity.path

    @property
    def version(self) -> str | None:
        return self.identity.version


@dataclass(frozen=True, slots=True)
class PiOAuthHelper:
    argv: tuple[str, ...]
    identity: PiRuntimeIdentity

    @property
    def path(self) -> Path:
        return self.identity.path


@dataclass(frozen=True, slots=True)
class PiRuntimeLock:
    path: Path
    repository: str
    commit: str
    package_name: str
    package_version: str
    package_directory: Path
    package_executable: Path
    oauth_helper: Path
    npm_integrity: str
    node_minimum: str
    pi_ai_version: str
    pi_ai_npm_integrity: str
    patches: tuple[PiRuntimePatch, ...]
    patches_sha256: str
    sha256: str

    @classmethod
    def load(cls, path: Path | None = None) -> Self:
        lock_path = (path or default_lock_path()).resolve()
        try:
            raw = lock_path.read_bytes()
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise PiRuntimeLockError("invalid runtime lock JSON") from exc
        except (OSError, UnicodeDecodeError) as exc:
            raise PiRuntimeLockError("runtime lock cannot be read") from exc

        cls._validate(data)
        package = data["package"]
        source = data["source"]
        runtime = data["runtime"]
        patches = cls._load_patches(lock_path, data.get("patches"))
        return cls(
            path=lock_path,
            repository=source["repository"],
            commit=source["commit"],
            package_name=package["name"],
            package_version=package["version"],
            package_directory=Path(package["directory"]),
            package_executable=Path(package["executable"]),
            oauth_helper=Path(package["oauth_helper"]),
            npm_integrity=package["npm_integrity"],
            node_minimum=runtime["node_minimum"],
            pi_ai_version=runtime["pi_ai_version"],
            pi_ai_npm_integrity=runtime["pi_ai_npm_integrity"],
            patches=patches,
            patches_sha256=cls._patches_sha256(lock_path, patches),
            sha256=hashlib.sha256(raw).hexdigest(),
        )

    @property
    def version(self) -> str:
        return self.package_version

    @property
    def executable(self) -> Path:
        return self.package_directory / self.package_executable

    @staticmethod
    def _validate(data: Any) -> None:
        if not isinstance(data, dict):
            raise PiRuntimeLockError("runtime lock must be a JSON object")
        if data.get("schema_version") != EXPECTED_SCHEMA_VERSION:
            raise PiRuntimeLockError("unsupported runtime lock schema version")
        source = data.get("source")
        package = data.get("package")
        runtime = data.get("runtime")
        if not isinstance(source, dict) or not isinstance(package, dict) or not isinstance(runtime, dict):
            raise PiRuntimeLockError("runtime lock is missing required sections")
        required_source = {"repository", "commit"}
        required_package = {
            "name",
            "version",
            "directory",
            "executable",
            "oauth_helper",
            "npm_integrity",
        }
        required_runtime = {"node_minimum", "pi_ai_version", "pi_ai_npm_integrity"}
        missing = required_source - source.keys()
        missing |= required_package - package.keys()
        missing |= required_runtime - runtime.keys()
        if missing:
            raise PiRuntimeLockError(
                "runtime lock missing required fields: " + ", ".join(sorted(missing))
            )
        if source["repository"] != "https://github.com/earendil-works/pi.git":
            raise PiRuntimeLockError("runtime lock repository is not pinned")
        if source["commit"] != "b79e4cc834970cca69daebffab7df1da7d1e52c4":
            raise PiRuntimeLockError("runtime lock commit is not pinned")
        if package["name"] != "@earendil-works/pi-coding-agent":
            raise PiRuntimeLockError("runtime lock package is not pinned")
        if package["version"] != "0.84.4":
            raise PiRuntimeLockError("runtime lock package version is not pinned")
        if runtime["pi_ai_version"] != "0.84.4":
            raise PiRuntimeLockError("runtime lock dependency version is not pinned")
        if runtime["pi_ai_npm_integrity"] != "sha512-AClAZxf5+c4RRu44NJPS6wyQy+Nmq+Mzyyrdvm4ZVMNuixelO02RZX4G4Aq1F145Yzp43wnM5S+hLlSI7ypfVw==":
            raise PiRuntimeLockError("runtime lock dependency integrity is not pinned")
        if package["npm_integrity"] != "sha512-jmOlrqUmvhh/siNWFRXjYLJzhKFIHNsAQaysRwzQPQFnPAaV/vhqHsLH/MBsIISA1Rjj7WTUFR3nJrpXoLx39w==":
            raise PiRuntimeLockError("runtime lock package integrity is not pinned")
        for field_name in ("directory", "executable", "oauth_helper"):
            _validate_package_path(package[field_name], field_name)

    @staticmethod
    def _load_patches(
        lock_path: Path, raw_patches: Any
    ) -> tuple[PiRuntimePatch, ...]:
        if not isinstance(raw_patches, list) or not raw_patches:
            raise PiRuntimeLockError("runtime lock patches must contain an entry")
        patches: list[PiRuntimePatch] = []
        config_dir = lock_path.parent.resolve()
        for raw_patch in raw_patches:
            if not isinstance(raw_patch, dict):
                raise PiRuntimeLockError("runtime lock patch must be an object")
            path_value = raw_patch.get("path")
            digest = raw_patch.get("sha256")
            if not isinstance(path_value, str) or not path_value:
                raise PiRuntimeLockError("runtime lock patch path must be text")
            if not isinstance(digest, str) or PATCH_SHA256_RE.fullmatch(digest) is None:
                raise PiRuntimeLockError("runtime lock patch digest is invalid")
            relative = Path(path_value)
            if relative.is_absolute():
                raise PiRuntimeLockError("runtime lock patch path must be relative")
            if ".." in relative.parts:
                raise PiRuntimeLockError("runtime lock patch path escapes its directory")
            patch_path = (config_dir / relative).resolve()
            try:
                patch_path.relative_to(config_dir)
                actual = hashlib.sha256(patch_path.read_bytes()).hexdigest()
            except (OSError, ValueError) as exc:
                raise PiRuntimeLockError("runtime lock patch cannot be read") from exc
            if actual != digest:
                raise PiRuntimeLockError("runtime lock patch digest mismatch")
            patches.append(PiRuntimePatch(path=patch_path, sha256=digest))
        return tuple(patches)

    @staticmethod
    def _patches_sha256(
        lock_path: Path, patches: tuple[PiRuntimePatch, ...]
    ) -> str:
        config_dir = lock_path.parent.resolve()
        payload = json.dumps(
            [
                {
                    "path": patch.path.relative_to(config_dir).as_posix(),
                    "sha256": patch.sha256,
                }
                for patch in patches
            ],
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def default_lock_path(root: Path | None = None) -> Path:
    base = Path.cwd() if root is None else Path(root)
    candidates = (
        base / "configs" / "runtime" / "pi-runtime.lock.json",
        base / "configs" / "pi-runtime.lock.json",
        base / "pi-runtime.lock.json",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def _validate_package_path(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise PiRuntimeLockError(
            f"runtime lock package {field_name} path must be non-empty"
        )
    if "\\" in value:
        raise PiRuntimeLockError(
            f"runtime lock package {field_name} path uses an invalid separator"
        )
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise PiRuntimeLockError(
            f"runtime lock package {field_name} path must be relative"
        )


__all__ = [
    "EXPECTED_SCHEMA_VERSION",
    "PiCommand",
    "PiOAuthHelper",
    "PiRuntimeIdentity",
    "PiRuntimeLock",
    "PiRuntimeLockError",
    "PiRuntimePatch",
    "default_lock_path",
]
