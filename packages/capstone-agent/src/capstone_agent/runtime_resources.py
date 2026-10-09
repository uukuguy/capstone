"""Immutable application resource profiles from project-owned native Pi settings."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

ROLES = frozenset({"harness_engine", "delegated_pi", "direct_pi"})


def content_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def safe_path(root: Path, name: str, *, base: Path | None = None) -> Path:
    """Confine local native references, including resolved links, to a trusted root."""
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise ValueError("resource path must be relative")
    path = ((base or root) / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("resource path escapes trusted root")
    return path


@dataclass(frozen=True, slots=True)
class ResourceDescriptor:
    resource_id: str
    kind: str
    version: str
    source: str
    roles: tuple[str, ...]
    enabled: bool
    installed: bool
    ready: bool
    reason: str | None
    required_tools: tuple[str, ...]
    loaded_identity: str | None

    def to_document(self) -> dict:
        return {"id": self.resource_id, "kind": self.kind, "version": self.version,
                "source": self.source, "roles": list(self.roles), "enabled": self.enabled,
                "installed": self.installed, "ready": self.ready, "reason": self.reason,
                "required_tools": list(self.required_tools), "loaded_identity": self.loaded_identity}


@dataclass(frozen=True, slots=True)
class ResolvedResourceProfile:
    profile_id: str
    revision: str
    role: str
    native_settings_paths: tuple[Path, ...]
    resources: tuple[ResourceDescriptor, ...]
    loaded_identities: tuple[tuple[str, str], ...]
    installation_id: str | None
    prepared_descriptor_json: str | None
    configuration_json: str

    def to_document(self) -> dict:
        return {"schema": "capstone-resource-profile/1", "profile_id": self.profile_id,
                "revision": self.revision, "role": self.role,
                "resources": [item.to_document() for item in self.resources]}


def _read_settings(path: Path, boundary: Path) -> tuple[dict[str, str], dict[str, str]]:
    settings = json.loads(path.read_text())
    skills: dict[str, str] = {}
    identities = {"settings": hashlib.sha256(path.read_bytes()).hexdigest()}
    for key in ("skills", "extensions", "packages"):
        entries = settings.get(key, [])
        if not isinstance(entries, list):
            raise ValueError(f"native {key} must be an array")
        if key == "skills" and (path.parent / "skills").exists():
            entries = ["skills", *entries]
        for entry in entries:
            # Installed packages must be local. Resolution never fetches npm/git sources.
            if not isinstance(entry, str):
                raise ValueError("native resource path must be a local string")
            target = safe_path(boundary, entry, base=path.parent)
            if not target.exists():
                continue
            files = (sorted(target.rglob("SKILL.md")) if target.is_dir() else [target]) if key == "skills" else []
            if key != "skills":
                identities[f"{key}:{entry}"] = _tree_identity(target, boundary)
            for skill in files:
                safe_path(boundary, str(skill.relative_to(boundary)))
                body = skill.read_text()
                frontmatter = re.match(r"\A---\s*\n(.*?)\n---", body, re.S)
                name = re.search(r"(?m)^name:\s*([A-Za-z0-9_-]+)\s*$", frontmatter.group(1)) if frontmatter else None
                if name is None:
                    raise ValueError("native skill needs a Pi name in SKILL.md")
                if name[1] in skills:
                    raise ValueError(f"duplicate skill name: {name[1]}")
                skills[name[1]] = _tree_identity(skill.parent, boundary)
    return skills, identities


def _tree_identity(path: Path, boundary: Path) -> str:
    files = sorted(path.rglob("*")) if path.is_dir() else [path]
    entries = {}
    for file in files:
        if file.is_symlink():
            raise ValueError("native resource path contains a link")
        if file.is_file():
            safe_path(boundary, str(file.relative_to(boundary)))
            entries[str(file.relative_to(path) if path.is_dir() else file.name)] = hashlib.sha256(file.read_bytes()).hexdigest()
    return content_hash(entries)


def resolve_resource_profile(config_root: Path, role: str) -> ResolvedResourceProfile:
    if role not in ROLES:
        raise ValueError("unknown resource role")
    root = config_root.resolve()
    manifest = json.loads((root / "agent-resources.json").read_text())
    if manifest.get("schema") != "capstone-agent-resources/1":
        raise ValueError("unsupported resource schema")
    binding = manifest["roles"][role]
    settings = safe_path(root, binding["settings"])
    skills, native = _read_settings(settings, root)
    if (root / "power-samples.lock.json").is_file():
        native["resource-lock"] = hashlib.sha256((root / "power-samples.lock.json").read_bytes()).hexdigest()
    paths = [settings]
    prepared = None
    managed_present = False
    prepared_reason = "managed installation is missing"
    managed = safe_path(root.parent.parent, ".grid-agent/runtime/agent-resources")
    if (managed / "current.json").exists():
        pointer = json.loads((managed / "current.json").read_text())
        managed_present = (safe_path(managed, pointer["install_id"]) / "prepared-mcp.json").is_file()
        from .resource_installation import inspect_installation
        prepared, prepared_reason = inspect_installation(managed)
        if prepared is not None:
            install = safe_path(managed, prepared["install_id"])
            native_path = install / "native" / role / "settings.json"
            loaded, installed_native = _read_settings(native_path, install)
            if skills.keys() & loaded.keys():
                raise ValueError("duplicate skill name across native settings")
            skills.update(loaded)
            native.update({"managed:" + key: value for key, value in installed_native.items()})
            paths.append(native_path)
    adapters = binding.get("adapters", {})
    available_tools: set[str] = set()
    valid_adapters: set[str] = set()
    for name, adapter in adapters.items():
        path = safe_path(root, adapter["path"])
        verification = adapter.get("verification")
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == adapter["sha256"] and verification:
            receipt_path = safe_path(root, verification["path"])
            if not receipt_path.is_file() or hashlib.sha256(receipt_path.read_bytes()).hexdigest() != verification["sha256"]:
                continue
            receipt = json.loads(receipt_path.read_text())
            if (receipt.get("schema") != "capstone-resource-adapter-check/1" or receipt.get("status") != "passed"
                    or receipt.get("role") != role or receipt.get("adapter_id") != name
                    or receipt.get("source_sha256") != adapter["sha256"]):
                continue
            published = set(receipt.get("published_tool_ids", []))
            if not set(adapter.get("tool_ids", [])) <= published:
                continue
            valid_adapters.add(name)
            available_tools.update(published)
            native["adapter:" + name] = adapter["sha256"]
            native["adapter-check:" + name] = verification["sha256"]
    descriptors = []
    ids: set[str] = set()
    for item in manifest["resources"]:
        if item["id"] in ids:
            raise ValueError("duplicate resource id")
        ids.add(item["id"])
        if role not in item["roles"]:
            continue
        if item["kind"] not in {"skill", "mcp", "plugin"}:
            raise ValueError("unknown resource kind")
        identity = skills.get(item.get("native_name")) if item["kind"] == "skill" else (content_hash(prepared) if prepared else None)
        installed = identity is not None or (item.get("managed", False) and managed_present)
        required = item["required_tools"]
        if isinstance(required, dict):
            required = required[role]
        reason = None
        if not item["enabled"]:
            reason = "disabled"
        elif not installed:
            reason = prepared_reason if item.get("managed") else "native resource is missing"
        elif item.get("managed") and prepared is None:
            reason = prepared_reason
        elif item.get("adapter") and item["adapter"] not in valid_adapters:
            reason = "execution adapter is unavailable"
        elif set(required) - available_tools:
            reason = "required tool is unavailable"
        descriptors.append(ResourceDescriptor(item["id"], item["kind"], item["version"], item["source"],
            tuple(item["roles"]), item["enabled"], installed, reason is None, reason,
            tuple(required), identity))
    public = [item.to_document() for item in descriptors]
    revision = content_hash({"manifest": manifest, "role": role, "native": native, "resources": public})
    return ResolvedResourceProfile(manifest["profile_id"], revision, role, tuple(paths), tuple(descriptors), tuple(sorted(native.items())),
        prepared["install_id"] if prepared else None,
        json.dumps(prepared, sort_keys=True, separators=(",", ":")) if prepared else None,
        json.dumps(manifest, sort_keys=True, separators=(",", ":")))
