"""Application-selected professional resource adapters over prepared bindings.

Native samples retain their Pi identity. Professional execution loads original
Domain Pack guidance and exact semantic contracts; it never loads native tools.
No Domain Pack source or state is sent to the native executor.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
import hashlib
import json
import re
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
    installation_id: str | None = None
    guide_json: str | None = None

    @property
    def guide_document(self) -> dict[str, Any]:
        if self.guide_json is None:
            raise ValueError('accepted Harness guide is unavailable')
        return json.loads(self.guide_json)


@dataclass(frozen=True, slots=True)
class HarnessResourceProfile:
    revision: str
    document_json: str
    binding_id: str | None
    guide_sha256: str | None
    backend_descriptor_sha256: str | None
    private_json: str | None = None

    def to_document(self) -> dict[str, Any]:
        return json.loads(self.document_json)

    def private_document(self) -> dict[str, Any]:
        if self.private_json is None:
            raise ValueError('Harness private selection is unavailable')
        return json.loads(self.private_json)


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
    guide = None
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
    private = None
    if binding_id and guide is not None:
        skill = next(item for item in resources if item['id'] == 'powerskills-pandapower')
        private = {'schema': 'capstone-harness-selection/1', 'profile_revision': revision,
            'skill_id': skill['id'], 'skill_version': skill['version'], 'binding_id': binding_id,
            'guide': guide, 'native_loaded_identity': skill['loaded_identity'],
            'installation_id': base.installation_id, 'backend_descriptor_sha256': descriptor_sha256}
    return HarnessResourceProfile(revision, json.dumps(public, sort_keys=True, separators=(",", ":")),
                                  binding_id, guide_sha256, descriptor_sha256,
                                  json.dumps(private) if private else None)


def parse_harness_selection(document: object) -> HarnessSkillSelection:
    """Validate bounded private catalog/ledger data without accessing runtime state."""
    keys = {'schema', 'profile_revision', 'skill_id', 'skill_version', 'binding_id', 'guide',
            'native_loaded_identity', 'installation_id', 'backend_descriptor_sha256'}
    if not isinstance(document, dict) or set(document) != keys or len(json.dumps(document).encode()) > 32768:
        raise ValueError('accepted Harness selection is invalid')
    if document['schema'] != 'capstone-harness-selection/1' or document['skill_id'] != 'powerskills-pandapower':
        raise ValueError('accepted Harness selection is invalid')
    for name in keys - {'guide', 'schema'}:
        if not isinstance(document[name], str) or not 1 <= len(document[name]) <= 256:
            raise ValueError('accepted Harness identity is invalid')
    for name in ('profile_revision', 'backend_descriptor_sha256'):
        if not re.fullmatch('[a-f0-9]{64}', document[name]):
            raise ValueError('accepted Harness hash is invalid')
    if not re.fullmatch('installs/[a-f0-9]{32}', document['installation_id']):
        raise ValueError('accepted Harness installation is invalid')
    if not re.fullmatch('[a-z][a-z0-9-]{0,63}', document['binding_id']):
        raise ValueError('accepted Harness binding is invalid')
    guide = document['guide']
    if (not isinstance(guide, dict) or set(guide) != {'resource_id', 'title', 'text', 'sha256'}
            or guide['resource_id'] != GUIDE_ID or any(not isinstance(value, str) for value in guide.values())
            or hashlib.sha256(guide['text'].encode()).hexdigest() != guide['sha256']):
        raise ValueError('accepted Harness guide identity changed')
    return HarnessSkillSelection(document['profile_revision'], document['skill_id'], document['skill_version'],
        document['binding_id'], GUIDE_ID, guide['sha256'], document['native_loaded_identity'],
        document['backend_descriptor_sha256'], document['installation_id'], json.dumps(guide))


def restore_harness_selection(config_root: Path, document: object) -> HarnessSkillSelection:
    """Resolve only trusted ledger/catalog bytes; a current pointer is not revocation."""
    from .resource_installation import inspect_installation
    selection = parse_harness_selection(document)
    current = json.loads((config_root / 'agent-resources.json').read_text())
    enabled = {item['id'] for item in current['resources'] if item['enabled'] and 'harness_engine' in item['roles']}
    if not {'powerskills-pandapower', 'powermcp-pandapower'} <= enabled:
        raise ValueError('accepted Harness resource was revoked')
    managed = config_root.parent.parent / '.grid-agent/runtime/agent-resources'
    descriptor, _ = inspect_installation(managed, install_id=selection.installation_id,
        expected_descriptor_sha256=selection.backend_descriptor_sha256)
    if descriptor is None:
        raise ValueError('accepted Harness installation is unavailable')
    return selection


def backend_environment(config_root: Path, installation_id: str, descriptor_sha256: str) -> dict[str, str]:
    return {'CAPSTONE_POWERMCP_MANAGED_ROOT': str(config_root.parent.parent / '.grid-agent/runtime/agent-resources'),
            'CAPSTONE_POWERMCP_INSTALL_ID': installation_id,
            'CAPSTONE_POWERMCP_DESCRIPTOR_SHA256': descriptor_sha256}


class _AcceptedGuideProvider:
    """Materialize an accepted pack-authored guide through the public guide SPI."""
    def __init__(self, provider, guide):
        self.provider, self.guide = provider, guide

    def load(self):
        other = tuple(item for item in self.provider.load() if item['resource_id'] != GUIDE_ID)
        return (*other, {key: value for key, value in self.guide.items() if key != 'text'})

    def open(self, resource_id):
        return dict(self.guide) if resource_id == GUIDE_ID else self.provider.open(resource_id)


def selected_application_profile(profile, claim):
    """Derive a claim-owned declaration before normal Kernel/Authority preparation."""
    from .pi_intent import default_config_root
    root = default_config_root().parent
    private = (claim.submission or {}).get('professional_resource')
    pending = (claim.submission or {}).get('_professional_backend')
    if private is None and pending is None:
        return profile
    selection = restore_harness_selection(root, private) if private is not None else None
    if selection is not None:
        install_id = selection.installation_id
        if install_id is None:
            raise ValueError('accepted Harness installation is unavailable')
        environment = backend_environment(root, install_id, selection.backend_descriptor_sha256)
    else:
        environment = pending
    domains = []
    for binding in profile.domains:
        select = getattr(binding.profile.provisioner, 'with_prepared_backend', None)
        if callable(select) and (selection is None or selection.binding_id == binding.binding_id):
            provider = binding.profile.guide_provider
            if selection is not None:
                provider = _AcceptedGuideProvider(provider, selection.guide_document)
            domain = replace(binding.profile, provisioner=select(environment), guide_provider=provider)
            binding = replace(binding, profile=domain)
        domains.append(binding)
    return replace(profile, domains=tuple(domains))


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
