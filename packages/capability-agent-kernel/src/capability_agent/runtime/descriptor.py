"""Binding-aware descriptor materialization for model-side transports."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
import re
from typing import Mapping


RUNTIME_DESCRIPTOR_SCHEMA = "capability-agent-runtime/1.0"
_DESCRIPTOR_FIELDS = frozenset(
    {
        "schema",
        "binding_id",
        "workspace_path",
        "application_workspace_path",
        "executable",
        "executable_args",
        "search_path",
        "protocol",
        "protocol_version",
        "authority_id",
        "tool_catalog_path",
        "guide_index_path",
        "guide_root_path",
        "core_tool_names",
        "guide_tool_name",
        "context_tool_name",
        "decision_tool_name",
        "tool_name_prefix",
        "guide_index_sha256",
    }
)
_SENSITIVE_NAME_PARTS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth_token",
        "authorization",
        "credential",
        "password",
        "secret",
        "token",
    }
)
_PROTOCOL_PATTERN = re.compile(r"^[a-z][a-z0-9.-]*$")
_PROTOCOL_VERSION_PATTERN = re.compile(r"^\d+\.\d+$")
_TOOL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_TOOL_PREFIX_PATTERN = re.compile(r"^[a-z][a-z0-9_]*_$")
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class RuntimeDescriptorError(ValueError):
    """Raised when a controller-owned runtime descriptor is unsafe."""


@dataclass(frozen=True, slots=True)
class RuntimeDescriptor:
    binding_id: str
    workspace_path: Path
    executable: str
    application_workspace_path: Path | None = None
    executable_args: tuple[str, ...] = ()
    search_path: tuple[str, ...] = ()
    protocol: str = ""
    protocol_version: str = ""
    authority_id: str = ""
    tool_catalog_path: Path | None = None
    guide_index_path: Path | None = None
    guide_root_path: Path | None = None
    core_tool_names: tuple[str, ...] = (
        "agent_record_decision",
        "agent_context_get",
    )
    guide_tool_name: str | None = None
    context_tool_name: str | None = None
    decision_tool_name: str | None = None
    tool_name_prefix: str | None = None
    guide_index_sha256: str | None = None
    application_id: str = "capability-agent"
    run_id: str = "run"
    pi_runtime: Mapping[str, str] | None = None
    active_turn_path: Path | None = None
    context_view_path: Path | None = None
    trajectory_requests_path: Path | None = None
    trajectory_capture_state_path: Path | None = None
    trajectory_allowed_refs_path: Path | None = None
    trajectory_acks_path: Path | None = None
    extra: Mapping[str, object] = field(default_factory=dict, repr=False)

    schema: str = RUNTIME_DESCRIPTOR_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != RUNTIME_DESCRIPTOR_SCHEMA:
            raise RuntimeDescriptorError("unsupported runtime descriptor schema")
        _portable_identifier(self.binding_id, "binding_id")
        workspace = _absolute_directory(self.workspace_path, "workspace_path")
        object.__setattr__(self, "workspace_path", workspace)
        _reject_existing_symlink(workspace, "workspace_path")
        application_workspace = _absolute_directory(
            self.application_workspace_path or workspace,
            "application_workspace_path",
        )
        object.__setattr__(self, "application_workspace_path", application_workspace)
        _reject_existing_symlink(application_workspace, "application_workspace_path")
        if (
            not isinstance(self.executable, str)
            or not self.executable
            or "/" in self.executable
            or "\\" in self.executable
        ):
            raise RuntimeDescriptorError("executable must be a basename")
        _text_tuple(self.executable_args, "executable_args")
        search = _text_tuple(self.search_path, "search_path")
        object.__setattr__(self, "executable_args", tuple(self.executable_args))
        object.__setattr__(self, "search_path", search)
        for argument in self.executable_args:
            if Path(argument).is_absolute() and not _is_inside(
                Path(argument), workspace
            ):
                raise RuntimeDescriptorError(
                    "executable_args path is outside workspace_path"
                )
            if Path(argument).is_absolute():
                _reject_existing_symlink(Path(argument), "executable_args path")
        for name, value in (
            ("protocol", self.protocol),
            ("protocol_version", self.protocol_version),
            ("authority_id", self.authority_id),
        ):
            if not isinstance(value, str):
                raise RuntimeDescriptorError(f"{name} must be text")
        if self.protocol and _PROTOCOL_PATTERN.fullmatch(self.protocol) is None:
            raise RuntimeDescriptorError("protocol is invalid")
        if self.protocol_version and _PROTOCOL_VERSION_PATTERN.fullmatch(
            self.protocol_version
        ) is None:
            raise RuntimeDescriptorError("protocol_version is invalid")
        if self.authority_id and _PROTOCOL_PATTERN.fullmatch(self.authority_id) is None:
            raise RuntimeDescriptorError("authority_id is invalid")
        for name in (
            "tool_catalog_path",
            "guide_index_path",
            "guide_root_path",
        ):
            value = getattr(self, name)
            if value is not None:
                _absolute_directory_or_file(value, name)
                path = Path(value)
                if not _is_inside(path, workspace):
                    raise RuntimeDescriptorError(
                        f"{name} is outside workspace_path"
                    )
                _reject_existing_symlink(path, name)
                object.__setattr__(self, name, path)
        _text_tuple(self.core_tool_names, "core_tool_names")
        object.__setattr__(self, "core_tool_names", tuple(self.core_tool_names))
        if self.tool_name_prefix is not None and _TOOL_PREFIX_PATTERN.fullmatch(
            self.tool_name_prefix
        ) is None:
            raise RuntimeDescriptorError("tool_name_prefix is invalid")
        for name in ("guide_tool_name", "context_tool_name", "decision_tool_name"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, str)
                or not value
                or _TOOL_NAME_PATTERN.fullmatch(value) is None
            ):
                raise RuntimeDescriptorError(f"{name} must be text")
        if self.guide_index_sha256 is not None and _SHA256_PATTERN.fullmatch(
            self.guide_index_sha256
        ) is None:
            raise RuntimeDescriptorError("guide_index_sha256 is invalid")
        for name in (
            "active_turn_path",
            "context_view_path",
            "trajectory_requests_path",
            "trajectory_capture_state_path",
            "trajectory_allowed_refs_path",
            "trajectory_acks_path",
        ):
            value = getattr(self, name)
            if value is not None:
                _absolute_directory_or_file(value, name)
                path = Path(value)
                if not _is_inside(path, application_workspace):
                    raise RuntimeDescriptorError(f"{name} is outside workspace_path")
                _reject_existing_symlink(path, name)
                object.__setattr__(self, name, path)
        capture_paths = (
            self.trajectory_requests_path,
            self.trajectory_capture_state_path,
            self.trajectory_allowed_refs_path,
            self.trajectory_acks_path,
        )
        if any(path is not None for path in capture_paths) and (
            any(path is None for path in capture_paths)
            or self.active_turn_path is None
        ):
            raise RuntimeDescriptorError("model request capture channels must be complete")
        if not isinstance(self.application_id, str) or not self.application_id:
            raise RuntimeDescriptorError("application_id must be non-empty text")
        if not isinstance(self.run_id, str) or not self.run_id:
            raise RuntimeDescriptorError("run_id must be non-empty text")
        if self.pi_runtime is not None:
            if not isinstance(self.pi_runtime, Mapping):
                raise RuntimeDescriptorError("pi_runtime must be an object")
            if any(not isinstance(key, str) or not isinstance(value, str) or not value for key, value in self.pi_runtime.items()):
                raise RuntimeDescriptorError("pi_runtime must contain text values")
        if not isinstance(self.extra, Mapping):
            raise RuntimeDescriptorError("extra must be an object")
        extra = dict(self.extra)
        overlap = _DESCRIPTOR_FIELDS.intersection(extra)
        if overlap:
            raise RuntimeDescriptorError(
                "descriptor extensions overwrite reserved fields: "
                + ", ".join(sorted(overlap))
            )
        _validate_extension_values(extra)
        object.__setattr__(self, "extra", extra)

    def as_json(self) -> dict[str, object]:
        if self.extra:
            raise RuntimeDescriptorError(
                "descriptor extensions are not supported by runtime schema"
            )
        if not self.protocol or not self.protocol_version or not self.authority_id:
            raise RuntimeDescriptorError(
                "protocol, protocol_version, and authority_id are required"
            )
        if len(self.core_tool_names) != 2:
            raise RuntimeDescriptorError(
                "core_tool_names must contain decision and context names"
            )
        decision_tool_name, context_tool_name = self.core_tool_names
        for name, value in (
            ("core decision tool", decision_tool_name),
            ("core context tool", context_tool_name),
        ):
            if _TOOL_NAME_PATTERN.fullmatch(value) is None or not value.startswith("agent_"):
                raise RuntimeDescriptorError(f"{name} must use the agent_ namespace")
        if decision_tool_name == context_tool_name:
            raise RuntimeDescriptorError("core tool names must be distinct")
        prefix = self.tool_name_prefix
        if prefix is None:
            portable = self.binding_id.replace("-", "_")
            prefix = f"{portable}_"
        if _TOOL_PREFIX_PATTERN.fullmatch(prefix) is None:
            raise RuntimeDescriptorError("tool_name_prefix is invalid")
        guide_tool_name = self.guide_tool_name or f"{prefix}guide_open"
        if (
            _TOOL_NAME_PATTERN.fullmatch(guide_tool_name) is None
            or not guide_tool_name.startswith(prefix)
            or not guide_tool_name.endswith("guide_open")
            or guide_tool_name.startswith("agent_")
        ):
            raise RuntimeDescriptorError("guide_tool_name is invalid")
        required_paths = {
            "tool_catalog_path": self.tool_catalog_path,
            "guide_index_path": self.guide_index_path,
            "guide_root_path": self.guide_root_path,
        }
        if any(path is None for path in required_paths.values()):
            raise RuntimeDescriptorError(
                "tool catalog, guide index, and guide root paths are required"
            )
        guide_digest = self.guide_index_sha256
        actual_guide_digest = _file_sha256(self.guide_index_path)
        if guide_digest is None:
            guide_digest = actual_guide_digest
        elif guide_digest != actual_guide_digest:
            raise RuntimeDescriptorError("guide_index_sha256 does not match guide index")
        if _SHA256_PATTERN.fullmatch(guide_digest) is None:
            raise RuntimeDescriptorError("guide_index_sha256 is invalid")
        core: dict[str, object] = {
            "decisionToolName": decision_tool_name,
            "contextToolName": context_tool_name,
        }
        for source, target in (
            (self.active_turn_path, "activeTurnPath"),
            (self.context_view_path, "analysisContextViewPath"),
            (self.trajectory_requests_path, "trajectoryRequestsPath"),
            (self.trajectory_capture_state_path, "trajectoryCaptureStatePath"),
            (self.trajectory_allowed_refs_path, "trajectoryAllowedRefsPath"),
            (self.trajectory_acks_path, "trajectoryAcksPath"),
        ):
            if source is not None:
                core[target] = str(source)
        domain: dict[str, object] = {
            "bindingId": self.binding_id,
            "protocol": self.protocol,
            "protocolVersion": self.protocol_version,
            "executable": self.executable,
            "executableArgs": list(self.executable_args),
            "toolCatalogPath": str(self.tool_catalog_path),
            "guideToolName": guide_tool_name,
            "guideIndexPath": str(self.guide_index_path),
            "guideRootPath": str(self.guide_root_path),
            "guideIndexSha256": guide_digest,
            "workspacePath": str(self.workspace_path),
            "authorityId": self.authority_id,
        }
        payload: dict[str, object] = {
            "schema": self.schema,
            "application": {
                "applicationId": self.application_id,
                "runId": self.run_id,
                "workspacePath": str(self.application_workspace_path),
                **(
                    {"piRuntime": dict(self.pi_runtime)}
                    if self.pi_runtime is not None
                    else {}
                ),
            },
            "core": core,
            "domains": [domain],
        }
        return payload


def write_runtime_descriptor(path: Path, descriptor: RuntimeDescriptor) -> Path:
    """Atomically write a private descriptor without following its leaf."""

    target = Path(path)
    if target.is_symlink():
        raise RuntimeDescriptorError("runtime descriptor must not be a symlink")
    _reject_symlink_ancestors(target.parent)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = (
        json.dumps(
            descriptor.as_json(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        + "\n"
    ).encode("utf-8")
    fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "wb") as stream:
            fd = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        directory_fd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as exc:
        raise RuntimeDescriptorError("runtime descriptor could not be written") from exc
    finally:
        if fd >= 0:
            os.close(fd)
        if temporary.exists():
            temporary.unlink()
    return target


def descriptor_from_endpoint(
    *,
    binding_id: str,
    workspace: Path,
    application_workspace_path: Path | None = None,
    endpoint: object,
    protocol: str = "",
    protocol_version: str = "",
    authority_id: str = "",
    tool_catalog_path: Path | None = None,
    guide_index_path: Path | None = None,
    guide_root_path: Path | None = None,
    tool_name_prefix: str | None = None,
    guide_index_sha256: str | None = None,
    application_id: str = "capability-agent",
    run_id: str = "run",
    pi_runtime: Mapping[str, str] | None = None,
    active_turn_path: Path | None = None,
    context_view_path: Path | None = None,
    trajectory_requests_path: Path | None = None,
    trajectory_capture_state_path: Path | None = None,
    trajectory_allowed_refs_path: Path | None = None,
    trajectory_acks_path: Path | None = None,
) -> RuntimeDescriptor:
    """Convert only controller-owned endpoint metadata into a descriptor."""

    metadata = getattr(endpoint, "metadata", endpoint)
    if not isinstance(metadata, Mapping):
        raise RuntimeDescriptorError("endpoint metadata must be an object")
    executable = metadata.get("executable")
    if not isinstance(executable, str):
        raise RuntimeDescriptorError("endpoint metadata must declare executable")
    raw_args = metadata.get("executable_args", metadata.get("arguments", ()))
    raw_search = metadata.get("search_path", metadata.get("search_paths", ()))
    raw_core_tools = metadata.get(
        "core_tool_names", ("agent_record_decision", "agent_context_get")
    )
    return RuntimeDescriptor(
        binding_id=binding_id,
        workspace_path=workspace,
        application_workspace_path=application_workspace_path,
        executable=executable,
        executable_args=tuple(_text_sequence(raw_args, "executable_args")),
        search_path=tuple(_text_sequence(raw_search, "search_path")),
        protocol=protocol or _optional_text(metadata.get("protocol")),
        protocol_version=protocol_version
        or _optional_text(metadata.get("protocol_version")),
        authority_id=authority_id or _optional_text(metadata.get("authority_id")),
        tool_catalog_path=tool_catalog_path
        or _optional_metadata_path(metadata.get("tool_catalog_path"), "tool_catalog_path"),
        guide_index_path=guide_index_path
        or _optional_metadata_path(metadata.get("guide_index_path"), "guide_index_path"),
        guide_root_path=guide_root_path
        or _optional_metadata_path(metadata.get("guide_root_path"), "guide_root_path"),
        core_tool_names=tuple(_text_sequence(raw_core_tools, "core_tool_names")),
        guide_tool_name=_optional_nullable_text(
            metadata.get("guide_tool_name"), "guide_tool_name"
        ),
        context_tool_name=_optional_nullable_text(
            metadata.get("context_tool_name"), "context_tool_name"
        ),
        decision_tool_name=_optional_nullable_text(
            metadata.get("decision_tool_name"), "decision_tool_name"
        ),
        tool_name_prefix=(
            tool_name_prefix
            if tool_name_prefix is not None
            else _optional_nullable_text(metadata.get("tool_name_prefix"), "tool_name_prefix")
        ),
        guide_index_sha256=(
            guide_index_sha256
            if guide_index_sha256 is not None
            else _optional_nullable_text(metadata.get("guide_index_sha256"), "guide_index_sha256")
        ),
        application_id=application_id,
        run_id=run_id,
        pi_runtime=pi_runtime,
        active_turn_path=active_turn_path,
        context_view_path=context_view_path,
        trajectory_requests_path=trajectory_requests_path,
        trajectory_capture_state_path=trajectory_capture_state_path,
        trajectory_allowed_refs_path=trajectory_allowed_refs_path,
        trajectory_acks_path=trajectory_acks_path,
    )


def _portable_identifier(value: object, field_name: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or not value[0].isalpha()
        or any(not (char.isalnum() or char in "-_") for char in value)
    ):
        raise RuntimeDescriptorError(f"{field_name} is not portable")


def _absolute_directory(value: Path, field_name: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise RuntimeDescriptorError(f"{field_name} must be absolute")
    return path


def _absolute_directory_or_file(value: Path, field_name: str) -> None:
    if not Path(value).is_absolute():
        raise RuntimeDescriptorError(f"{field_name} must be absolute")


def _is_inside(path: Path, root: Path) -> bool:
    try:
        Path(path).absolute().relative_to(Path(root).absolute())
    except ValueError:
        return False
    return True


def _reject_existing_symlink(path: Path, field_name: str) -> None:
    current = path
    while True:
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            parent = current.parent
            if parent == current:
                return
            current = parent
            continue
        except OSError as exc:
            raise RuntimeDescriptorError(
                f"{field_name} cannot be inspected"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise RuntimeDescriptorError(f"{field_name} must not contain symlinks")
        parent = current.parent
        if parent == current:
            return
        current = parent


def _text_tuple(value: object, field_name: str) -> tuple[str, ...]:
    return tuple(_text_sequence(value, field_name))


def _text_sequence(value: object, field_name: str) -> list[str]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise RuntimeDescriptorError(f"{field_name} must be a string sequence")
    result = list(value)
    if any(not isinstance(item, str) or not item for item in result):
        raise RuntimeDescriptorError(f"{field_name} must contain non-empty strings")
    return result


def _optional_text(value: object) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise RuntimeDescriptorError("endpoint metadata contains non-text identity")
    return value


def _optional_nullable_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise RuntimeDescriptorError(f"{field_name} must be text")
    return value


def _optional_metadata_path(value: object, field_name: str) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, (str, Path)) or not str(value):
        raise RuntimeDescriptorError(f"{field_name} must be a path")
    return Path(value)


def _optional_path(value: Path | None) -> str | None:
    return str(value) if value is not None else None


def _file_sha256(path: Path | None) -> str:
    if path is None:
        raise RuntimeDescriptorError("guide index path is required")
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise RuntimeDescriptorError("guide index must be a regular file")
        digest = sha256()
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except RuntimeDescriptorError:
        raise
    except OSError as exc:
        raise RuntimeDescriptorError("guide index could not be read") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _reject_symlink_ancestors(path: Path) -> None:
    """Reject symlinked parent components before creating or replacing files."""

    current = Path(path)
    pending: list[Path] = []
    while True:
        try:
            current.lstat()
            break
        except FileNotFoundError:
            pending.append(current)
            parent = current.parent
            if parent == current:
                return
            current = parent
        except OSError as exc:
            raise RuntimeDescriptorError(
                "runtime descriptor directory cannot be inspected"
            ) from exc
    while True:
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise RuntimeDescriptorError(
                "runtime descriptor directory cannot be inspected"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise RuntimeDescriptorError(
                "runtime descriptor directory must not contain symlinks"
            )
        parent = current.parent
        if parent == current:
            break
        current = parent


def _validate_extension_values(value: object, *, active: set[int] | None = None) -> None:
    """Ensure descriptor extensions are JSON-safe and contain no credentials."""

    active = set() if active is None else active
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in active:
            raise RuntimeDescriptorError("descriptor extensions contain a cycle")
        active.add(identity)
        try:
            for key, item in value.items():
                if not isinstance(key, str):
                    raise RuntimeDescriptorError(
                        "descriptor extension keys must be text"
                    )
                if _sensitive_name(key):
                    raise RuntimeDescriptorError(
                        "descriptor extensions must not contain credentials"
                    )
                _validate_extension_values(item, active=active)
        finally:
            active.remove(identity)
        return
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in active:
            raise RuntimeDescriptorError("descriptor extensions contain a cycle")
        active.add(identity)
        try:
            for item in value:
                _validate_extension_values(item, active=active)
        finally:
            active.remove(identity)
        return
    if value is None or type(value) in {str, bool, int, float}:
        if isinstance(value, float) and (value != value or value in {float("inf"), float("-inf")}):
            raise RuntimeDescriptorError("descriptor extensions must contain finite numbers")
        return
    raise RuntimeDescriptorError("descriptor extensions must be JSON-compatible")


def _sensitive_name(value: str) -> bool:
    normalized = value.lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_NAME_PARTS)


__all__ = [
    "RUNTIME_DESCRIPTOR_SCHEMA",
    "RuntimeDescriptor",
    "RuntimeDescriptorError",
    "descriptor_from_endpoint",
    "write_runtime_descriptor",
]
