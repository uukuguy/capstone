from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from capability_agent._safe_files import write_bound_text


_RESOURCE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]+$")
_ENCODED_SEPARATOR_PATTERN = re.compile(r"%(?:2f|5c)", re.IGNORECASE)
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_SCHEMA_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
_DEFAULT_SCHEMA_ID = "capability-guide-index"
# Keep model-facing guide snapshots bounded before any bytes are published.
_MAX_GUIDE_RESOURCES = 64
_MAX_GUIDE_DOCUMENT_BYTES = 256 * 1024
_MAX_GUIDE_TOTAL_BYTES = 1024 * 1024
_MAX_GUIDE_TITLE_CHARS = 256


class GuideNotFound(KeyError):
    """Raised when a guide document is not published by the allowlist index."""


class GuideMaterializationError(RuntimeError):
    """Raised when a domain guide provider cannot publish a safe snapshot."""


@dataclass(frozen=True)
class GuideDocument:
    resource_id: str
    title: str
    text: str
    path: Path


class GuideIndex:
    def __init__(
        self,
        skill_root: Path,
        resources: dict[str, Path],
        *,
        protocol: str | None = None,
    ) -> None:
        self._skill_root = skill_root
        self._resources = dict(resources)
        self._protocol = _resolve_schema_id(protocol)

    @classmethod
    def load(
        cls,
        skill_root: Path,
        *,
        protocol: str | None = None,
    ) -> GuideIndex:
        root = Path(skill_root).resolve()
        resources: dict[str, Path] = {}

        overview = root / "SKILL.md"
        if overview.is_file():
            resources["overview"] = overview.resolve()

        references = root / "references"
        if references.is_dir():
            for path in sorted(references.iterdir(), key=lambda item: item.name):
                if path.is_file() and path.suffix == ".md":
                    resources[path.stem] = path.resolve()

        return cls(root, resources, protocol=protocol)

    def open(self, resource_id: str) -> GuideDocument:
        if (
            not _RESOURCE_ID_PATTERN.fullmatch(resource_id)
            or _ENCODED_SEPARATOR_PATTERN.search(resource_id)
        ):
            raise GuideNotFound(resource_id)

        path = self._resources.get(resource_id)
        if path is None or not path.is_relative_to(self._skill_root):
            raise GuideNotFound(resource_id)

        text = path.read_text(encoding="utf-8")
        return GuideDocument(
            resource_id=resource_id,
            title=_extract_title(text, fallback=resource_id),
            text=text,
            path=path,
        )

    def materialize(self, path: Path) -> Path:
        target = Path(path)
        payload = {
            "protocol": self._protocol,
            "version": "1.0",
            "root": str(self._skill_root),
            "resources": {
                resource_id: str(resource_path)
                for resource_id, resource_path in sorted(self._resources.items())
            },
        }
        try:
            write_bound_text(
                target,
                json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            )
        except OSError as exc:
            raise GuideMaterializationError("guide index could not be materialized safely") from exc
        return target


def materialize_guide_provider(
    provider: object,
    *,
    workspace: Path,
    guide_root_path: Path,
    guide_index_path: Path,
    protocol: str | None = None,
) -> Path:
    """Publish a provider's allowlisted documents into a binding snapshot.

    A Domain Pack owns the source resources and exposes only ``load`` and
    ``open``.  The Kernel copies the verified text into a fresh, binding-owned
    tree; the model receives paths in that tree and never receives the
    provider's source paths.  Every leaf is published without replacement.
    """

    workspace_path = _absolute_path(workspace, "guide workspace")
    root = _absolute_path(guide_root_path, "guide root")
    index_path = _absolute_path(guide_index_path, "guide index")
    _ensure_directory(workspace_path, "guide workspace")
    _assert_inside(root, workspace_path, "guide root")
    _assert_inside(index_path, workspace_path, "guide index")
    _reject_symlink_ancestors(root, "guide root")
    _reject_symlink_ancestors(index_path.parent, "guide index directory")
    _assert_absent(root, "guide snapshot root")
    _assert_absent(index_path, "guide index")

    documents = _load_provider_documents(provider)
    schema_id = _resolve_schema_id(protocol)
    payload_resources: dict[str, str] = {}
    materialized: list[tuple[Path, bytes]] = []
    for resource_id, _title, _digest, text in documents:
        relative = Path("SKILL.md") if resource_id == "overview" else Path(
            "references", f"{resource_id}.md"
        )
        target = root / relative
        payload_resources[resource_id] = str(target)
        materialized.append((target, text.encode("utf-8")))

    created_root = False
    root_identity: tuple[int, int] | None = None
    try:
        _mkdir_exclusive(root, "guide snapshot root")
        created_root = True
        root_identity = _directory_identity(root)
        references = root / "references"
        if any(path.parent == references for path, _content in materialized):
            _mkdir_exclusive(references, "guide references directory")
        for target, content in materialized:
            _write_exclusive(target, content)
        _ensure_directory(index_path.parent, "guide index directory")
        payload = {
            "protocol": schema_id,
            "version": "1.0",
            "root": str(root),
            "resources": {
                resource_id: payload_resources[resource_id]
                for resource_id in sorted(payload_resources)
            },
        }
        _write_exclusive(
            index_path,
            (
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8"),
        )
    except GuideMaterializationError:
        if created_root:
            _remove_created_snapshot(root, root_identity)
        raise
    except (OSError, ValueError, TypeError) as exc:
        if created_root:
            _remove_created_snapshot(root, root_identity)
        raise GuideMaterializationError("guide snapshot could not be published") from exc
    return index_path


def _load_provider_documents(
    provider: object,
) -> tuple[tuple[str, str, str, str], ...]:
    load = getattr(provider, "load", None)
    open_resource = getattr(provider, "open", None)
    if not callable(load) or not callable(open_resource):
        raise GuideMaterializationError(
            "guide provider must expose load() and open(resource_id)"
        )
    try:
        raw_index = load()
    except Exception:
        raise GuideMaterializationError("guide provider index could not be loaded") from None
    if not isinstance(raw_index, (tuple, list)):
        raise GuideMaterializationError("guide provider index must be a sequence")
    if len(raw_index) > _MAX_GUIDE_RESOURCES:
        raise GuideMaterializationError("guide provider resource count exceeds limit")

    documents: list[tuple[str, str, str, str]] = []
    seen: set[str] = set()
    total_bytes = 0
    for item in raw_index:
        if not isinstance(item, Mapping):
            raise GuideMaterializationError("guide provider index contains an invalid document")
        resource_id = item.get("resource_id")
        title = item.get("title")
        digest = item.get("sha256")
        if type(resource_id) is not str:
            raise GuideMaterializationError("guide provider resource ID is not portable")
        _validate_resource_id(resource_id)
        if resource_id in seen:
            raise GuideMaterializationError("guide provider index contains duplicate resource IDs")
        if type(title) is not str or not title:
            raise GuideMaterializationError("guide provider title must be non-empty text")
        if len(title) > _MAX_GUIDE_TITLE_CHARS:
            raise GuideMaterializationError("guide provider title exceeds limit")
        if type(digest) is not str or _SHA256_PATTERN.fullmatch(digest) is None:
            raise GuideMaterializationError("guide provider digest is invalid")
        seen.add(resource_id)
        try:
            opened = open_resource(resource_id)
        except Exception:
            raise GuideMaterializationError("guide provider document could not be opened") from None
        if not isinstance(opened, Mapping):
            raise GuideMaterializationError("guide provider document must be an object")
        opened_id = opened.get("resource_id")
        opened_title = opened.get("title")
        opened_digest = opened.get("sha256")
        text = opened.get("text")
        if (
            type(opened_id) is not str
            or opened_id != resource_id
            or type(opened_title) is not str
            or opened_title != title
            or type(opened_digest) is not str
            or opened_digest != digest
            or type(text) is not str
        ):
            raise GuideMaterializationError("guide provider document does not match its index")
        if len(opened_title) > _MAX_GUIDE_TITLE_CHARS:
            raise GuideMaterializationError("guide provider title exceeds limit")
        encoded_text = text.encode("utf-8")
        document_bytes = len(encoded_text)
        if document_bytes > _MAX_GUIDE_DOCUMENT_BYTES:
            raise GuideMaterializationError("guide provider document size exceeds limit")
        total_bytes += document_bytes
        if total_bytes > _MAX_GUIDE_TOTAL_BYTES:
            raise GuideMaterializationError("guide provider total size exceeds limit")
        if sha256(encoded_text).hexdigest() != digest:
            raise GuideMaterializationError("guide provider document digest does not match its index")
        documents.append((resource_id, title, digest, text))
    return tuple(documents)


def _validate_resource_id(value: object) -> None:
    if (
        type(value) is not str
        or _RESOURCE_ID_PATTERN.fullmatch(value) is None
        or _ENCODED_SEPARATOR_PATTERN.search(value)
    ):
        raise GuideMaterializationError("guide provider resource ID is not portable")


def _absolute_path(value: Path, label: str) -> Path:
    try:
        path = Path(os.path.abspath(os.fspath(value)))
    except (OSError, TypeError, ValueError) as exc:
        raise GuideMaterializationError(f"{label} is invalid") from exc
    if not path.is_absolute():
        raise GuideMaterializationError(f"{label} must be absolute")
    return path


def _assert_inside(path: Path, root: Path, label: str) -> None:
    try:
        path.relative_to(root)
    except ValueError:
        raise GuideMaterializationError(f"{label} escapes guide workspace") from None


def _reject_symlink_ancestors(path: Path, label: str) -> None:
    current = Path(path)
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
            raise GuideMaterializationError(f"{label} cannot be inspected") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise GuideMaterializationError(f"{label} must not contain symlinks")
        if not stat.S_ISDIR(metadata.st_mode):
            raise GuideMaterializationError(f"{label} must be a directory")
        parent = current.parent
        if parent == current:
            return
        current = parent


def _ensure_directory(path: Path, label: str) -> None:
    _reject_symlink_ancestors(path.parent, label)
    try:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError as exc:
        raise GuideMaterializationError(f"{label} could not be created") from exc
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise GuideMaterializationError(f"{label} cannot be inspected") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise GuideMaterializationError(f"{label} must be a directory")


def _assert_absent(path: Path, label: str) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise GuideMaterializationError(f"{label} cannot be inspected") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise GuideMaterializationError(f"{label} must not be a symlink")
    raise GuideMaterializationError(f"{label} already exists")


def _mkdir_exclusive(path: Path, label: str) -> None:
    _reject_symlink_ancestors(path.parent, label)
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        raise GuideMaterializationError(f"{label} already exists") from None
    except OSError as exc:
        raise GuideMaterializationError(f"{label} could not be created") from exc
    _fsync_directory(path.parent)


def _write_exclusive(path: Path, content: bytes) -> None:
    _reject_symlink_ancestors(path.parent, "guide snapshot file")
    descriptor: int | None = None
    temporary: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", dir=path.parent
        )
        temporary = Path(temporary_name)
        os.fchmod(descriptor, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError:
            raise GuideMaterializationError("guide snapshot file already exists") from None
        _fsync_directory(path.parent)
    except GuideMaterializationError:
        raise
    except OSError as exc:
        raise GuideMaterializationError("guide snapshot file could not be published") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def _directory_identity(path: Path) -> tuple[int, int]:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise GuideMaterializationError("guide snapshot root cannot be inspected") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise GuideMaterializationError("guide snapshot root must be a directory")
    return metadata.st_dev, metadata.st_ino


def _remove_created_snapshot(
    root: Path, identity: tuple[int, int] | None
) -> None:
    if identity is None:
        return
    try:
        metadata = root.lstat()
    except (FileNotFoundError, OSError):
        return
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISDIR(metadata.st_mode)
        or (metadata.st_dev, metadata.st_ino) != identity
    ):
        return
    try:
        shutil.rmtree(root)
    except OSError:
        pass


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError as exc:
        raise GuideMaterializationError("guide snapshot directory could not be synced") from exc
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _resolve_schema_id(schema_id: str | None) -> str:
    value = _DEFAULT_SCHEMA_ID if schema_id is None else schema_id
    if not isinstance(value, str) or not _SCHEMA_ID_PATTERN.fullmatch(value):
        raise ValueError("protocol is invalid")
    return value


def _extract_title(text: str, *, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback
