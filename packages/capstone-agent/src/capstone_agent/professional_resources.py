"""Application-selected professional resource adapters over prepared bindings.

Native samples retain their Pi identity. Professional execution loads original
Domain Pack guidance and exact semantic contracts; it never loads native tools.
No Domain Pack source or state is sent to the native executor.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from capability_agent.tools.guide import GuideIndex
from capability_agent.application.composition import PreparedBinding
from capability_agent.runtime.environment import PiLaunch
from .runtime_resources import content_hash, resolve_resource_profile


GUIDE_ID = "powerskills-pandapower-adapter"
ADAPTER_ID = "capstone-powerskills-pandapower/1"
SEMANTIC_TOOLS = ("model.list", "context.open", "context.get", "model.element.get", "analysis.run",
                  "model.dataset.list", "model.dataset.describe", "model.dataset.query", "model.constraints.describe",
                  "analysis.operation.describe", "analysis.powerflow.ac.run", "analysis.result.violations.evaluate",
                  "analysis.contingency.n_minus_one.run", "result.dataset.describe", "result.dataset.query")


def prepared_authority_environment(endpoints: Iterable[object]) -> dict[str, str]:
    """Compose only the fixed professional backend settings prepared by packs."""
    names = ("CAPSTONE_POWERMCP_MANAGED_ROOT", "CAPSTONE_POWERMCP_INSTALL_ID",
             "CAPSTONE_POWERMCP_DESCRIPTOR_SHA256")
    selected: dict[str, str] = {}
    for endpoint in endpoints:
        metadata = getattr(endpoint, "metadata", {})
        environment = metadata.get("environment", {}) if isinstance(metadata, Mapping) else {}
        if not isinstance(environment, Mapping):
            raise ValueError("prepared Authority environment is invalid")
        for name in names:
            if name not in environment:
                continue
            value = environment[name]
            if not isinstance(value, str) or not value:
                raise ValueError("prepared Authority runtime setting is invalid")
            if name in selected and selected[name] != value:
                raise ValueError("prepared Authority runtime settings conflict")
            selected[name] = value
    return selected


@dataclass(frozen=True, slots=True)
class HarnessSkillSelection:
    profile_revision: str
    skill_id: str
    skill_version: str
    binding_id: str
    guide_resource_id: str
    guide_sha256: str
    native_loaded_identity: str
    backend_descriptor_sha256: str


@dataclass(frozen=True, slots=True)
class HarnessResourceProfile:
    revision: str
    document_json: str
    binding_id: str | None
    guide_sha256: str | None
    backend_descriptor_sha256: str | None

    def to_document(self) -> dict[str, Any]:
        return json.loads(self.document_json)


def _guide(runtime: Any) -> dict[str, Any]:
    document = GuideIndex.load(runtime.guide_root_path).open(GUIDE_ID)
    return {"resource_id": GUIDE_ID, "title": document.title, "text": document.text,
            "sha256": hashlib.sha256(document.text.encode()).hexdigest()}


def resolve_harness_resource_profile(config_root: Path, bindings: Mapping[str, PreparedBinding]) -> HarnessResourceProfile:
    """Project actual prepared professional readiness with no private paths."""
    base = resolve_resource_profile(config_root, "harness_engine")
    binding_id = None
    guide_sha256 = None
    descriptor_sha256 = None
    reason = "selected professional adapter is unavailable"
    for candidate, binding in sorted(bindings.items()):
        runtime = binding.runtime
        published = {document.get("id") for document in runtime.capability_documents}
        if not set(SEMANTIC_TOOLS) <= published:
            continue
        try:
            guide = _guide(runtime)
            operation = runtime.executor.invoke("analysis.operation.describe", {"operation": "diagnostic.structural"})
            available = operation.get("availability", {})
            if not isinstance(available, dict):
                raise ValueError("invalid professional operation availability")
            if available.get("status") != "available":
                reason = "structural audit backend is unavailable"
                continue
            prepared = json.loads(base.prepared_descriptor_json) if base.prepared_descriptor_json else None
            if prepared is None or content_hash(prepared) != available.get("descriptor_sha256"):
                reason = "professional backend differs from the installed resource"
                continue
            binding_id, guide_sha256, descriptor_sha256 = candidate, guide["sha256"], available["descriptor_sha256"]
            reason = None
            break
        except Exception:
            # Runtime errors remain bounded, public readiness reasons.
            reason = "professional guide or operation verification failed"
    resources = []
    for resource in base.resources:
        item = resource.to_document()
        if resource.resource_id in {"powerskills-pandapower", "powermcp-pandapower"}:
            required = list(SEMANTIC_TOOLS) if resource.kind == "skill" else ["analysis.operation.describe", "analysis.run"]
            item["required_tools"] = required
            resource_reason = ("disabled" if not resource.enabled else "managed resource is unavailable"
                               if not resource.installed or not resource.loaded_identity else reason)
            item["ready"] = resource_reason is None
            item["reason"] = resource_reason
        else:
            item["ready"] = False
            item["reason"] = "professional execution adapter is unavailable"
        resources.append(item)
    public = {"schema": "capstone-resource-profile/1", "profile_id": base.profile_id,
              "role": "harness_engine", "resources": resources}
    revision = content_hash({"profile": public, "native_profile_revision": base.revision,
        "binding_id": binding_id, "adapter_id": ADAPTER_ID, "guide_sha256": guide_sha256,
        "backend_descriptor_sha256": descriptor_sha256})
    public["revision"] = revision
    return HarnessResourceProfile(revision, json.dumps(public, sort_keys=True, separators=(",", ":")),
                                  binding_id, guide_sha256, descriptor_sha256)


def bind_harness_skill(profile: HarnessResourceProfile, *, skill_id: str, skill_version: str,
                       profile_revision: str) -> HarnessSkillSelection:
    """Accept an explicit immutable skill/version/profile choice."""
    if not isinstance(profile, HarnessResourceProfile) or profile_revision != profile.revision:
        raise ValueError("Harness resource profile revision does not match")
    if skill_id != "powerskills-pandapower":
        raise ValueError("Harness skill adapter is unavailable")
    item = next((r for r in profile.to_document()["resources"] if r["id"] == skill_id and r["kind"] == "skill"), None)
    if item is None or item["version"] != skill_version:
        raise ValueError("Harness skill identity does not match")
    if not item["ready"] or not profile.binding_id or not profile.guide_sha256 or not profile.backend_descriptor_sha256:
        raise ValueError("Harness skill is unavailable")
    return HarnessSkillSelection(profile.revision, skill_id, skill_version, profile.binding_id,
        GUIDE_ID, profile.guide_sha256, item["loaded_identity"], profile.backend_descriptor_sha256)


def load_harness_skill(selection: HarnessSkillSelection, bindings: Mapping[str, PreparedBinding]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load the accepted prepared guide and recheck the frozen Authority backend."""
    if (not isinstance(selection, HarnessSkillSelection) or selection.guide_resource_id != GUIDE_ID
        or selection.skill_id != "powerskills-pandapower"):
        raise ValueError("invalid Harness skill selection")
    if selection.binding_id not in bindings:
        raise ValueError("selected Harness skill binding is unavailable")
    runtime = bindings[selection.binding_id].runtime
    guide = _guide(runtime)
    if guide["sha256"] != selection.guide_sha256:
        raise ValueError("selected Harness guide identity changed")
    published = {document.get("id") for document in runtime.capability_documents}
    if not set(SEMANTIC_TOOLS) <= published:
        raise ValueError("selected Harness semantic tool is unavailable")
    operation = runtime.executor.invoke("analysis.operation.describe", {"operation": "diagnostic.structural"})
    backend = operation.get("availability", {})
    if not isinstance(backend, dict):
        raise ValueError("invalid selected Harness backend availability")
    if backend.get("status") != "available" or backend.get("descriptor_sha256") != selection.backend_descriptor_sha256:
        raise ValueError("selected Harness backend identity changed")
    receipt = {"schema": "capstone-harness-skill-load/1", "status": "loaded", "role": "harness_engine",
               "profile_revision": selection.profile_revision, "skill_id": selection.skill_id,
               "skill_version": selection.skill_version, "binding_id": selection.binding_id,
               "adapter_id": ADAPTER_ID, "guide_resource_id": GUIDE_ID, "guide_sha256": guide["sha256"],
               "native_loaded_identity": selection.native_loaded_identity,
               "backend_descriptor_sha256": selection.backend_descriptor_sha256,
               "published_tool_ids": list(SEMANTIC_TOOLS)}
    return guide, receipt


def apply_harness_skill(launch: PiLaunch, selection: HarnessSkillSelection, bindings: Mapping[str, PreparedBinding],
                        attempt_path: Path) -> PiLaunch:
    """Load the accepted adapter into this professional launch and save receipt."""
    guide, receipt = load_harness_skill(selection, bindings)
    argv = list(launch.argv)
    try:
        position = argv.index("--system-prompt") + 1
        source = Path(argv[position]).read_text()
    except (ValueError, IndexError, OSError) as exc:
        raise ValueError("Harness system policy is unavailable") from exc
    attempt_path.mkdir(parents=True, exist_ok=True, mode=0o700)
    policy = attempt_path / "selected-skill-policy.md"
    policy.write_text(source + "\n\nSelected professional skill: " + selection.skill_id + "\n\n" + guide["text"])
    policy.chmod(0o600)
    receipt_path = attempt_path / "harness-skill-load.json"
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    receipt_path.chmod(0o600)
    argv[position] = str(policy)
    return PiLaunch(tuple(argv), dict(launch.environment))
