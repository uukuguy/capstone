"""Public Kernel SPI for target-owned PyPSA sector coupling."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from capability_agent.application.profile import DomainBinding
from capability_agent.application.reference_handoff import (
    ReferenceHandoffReceipt, resolve_handoff_receipt,
)
from capability_agent.domain import DomainManifest, DomainRuntimeProfile
from capability_agent.domain.answer_admission import AnswerAdmissionDecision, AnswerAdmissionInput
from capability_agent.domain.contracts import FilesystemCapabilityContractSource
from capability_agent.domain.output import CommittedAnswer
from capability_agent.domain.projection import VerifiedInvocation
from capability_agent.domain.provisioning import CredentialLease
from capability_agent.domain.state import DomainContextView
from capability_agent.tools.catalog import describe_tool_document
from capability_agent.tools.guide import GuideNotFound
from capability_agent.trajectory.answers import AnswerClaim, AnswerSubmission
from pypsa_model_authority.references import (
    VerifiedDocument, verify_model, verify_sector_evidence, verify_sector_result,
)


ROOT = Path(__file__).parent / "resources"
CONTRACT_ROOT = ROOT / "capabilities"
POLICY_PATH = ROOT / "policy" / "system-policy.md"
GUIDE_ROOT = ROOT / "guides"
_EXECUTABLE = "pypsasectorctl.exe" if os.name == "nt" else "pypsasectorctl"
_ENV_NAMES = frozenset({
    "PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TMPDIR", "TMP", "TEMP",
    "SYSTEMROOT", "SystemRoot", "WINDIR", "windir", "PATHEXT",
    "PYTHONIOENCODING", "PYTHONUTF8", "PYTHONUNBUFFERED", "PYTHONDONTWRITEBYTECODE",
    "CAPSTONE_PYPSA_MODEL_LIBRARY_DIR",
})


def _reference(value: object, kind: str) -> str:
    prefix = f"pypsa-{kind}:sha256:"
    if not isinstance(value, str) or not value.startswith(prefix) or len(value) != len(prefix) + 64:
        raise ValueError(f"PyPSA {kind} reference is invalid")
    if any(character not in "0123456789abcdef" for character in value[len(prefix):]):
        raise ValueError(f"PyPSA {kind} reference is invalid")
    return value


def _clean_environment() -> dict[str, str]:
    excluded = {
        name.strip() for name in os.environ.get("CAPABILITY_AGENT_SECRET_ENV_NAMES", "").split(",")
        if name.strip()
    }
    clean = {name: value for name, value in os.environ.items() if name in _ENV_NAMES and name not in excluded}
    clean["POLARS_MAX_THREADS"] = "4"
    return clean


class SectorExecutor:
    def __init__(
        self, *, executable: Path, workspace: Path, source_binding_id: str,
        timeout_seconds: float = 180.0,
    ) -> None:
        self.executable = Path(executable)
        self.workspace = Path(workspace)
        self.source_workspace = self.workspace.parent / source_binding_id
        self.run_id = self.workspace.parent.parent.name
        self.timeout_seconds = timeout_seconds
        self.environment = _clean_environment()
        self.last_diagnostics = ""

    def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]:
        if capability == "environment.describe":
            if arguments:
                raise ValueError("environment.describe takes no arguments")
            passed = {}
        else:
            expected = {"reference", "handoff_ref"}
            if capability not in {
                "sector.hydrogen_balance", "sector.heat_balance", "sector.hydrogen_storage",
                "sector.heat_storage", "sector.multiport_balance",
            } or set(arguments) != expected:
                raise ValueError("sector arguments do not match the contract")
            reference = _reference(arguments["reference"], "model")
            receipt_ref = arguments["handoff_ref"]
            if not isinstance(receipt_ref, str):
                raise ValueError("handoff receipt is invalid")
            receipt = resolve_handoff_receipt(
                self.workspace.parent.parent / "core" / "context-events.jsonl",
                receipt_ref, expected_run_id=self.run_id,
            )
            if (
                receipt.source_binding_id != self.source_workspace.name
                or receipt.target_binding_id != self.workspace.name
                or receipt.reference != reference
                or receipt.reference_kind != "model"
                or receipt.purpose != "sector"
                or receipt.capability_family != "sector"
                or receipt.authority_id != "pypsamodelctl"
                or receipt.revision_digest != reference.removeprefix("pypsa-model:sha256:")
            ):
                raise ValueError("handoff receipt does not authorize this sector solve")
            verify_model(self.source_workspace, self.run_id, reference)
            passed: dict[str, object] = {"model_ref": reference}
        request_id = f"pypsa-sector-{uuid4().hex}"
        request = {
            "protocol": "pypsa-sector-capability", "protocol_version": "1.0",
            "request_id": request_id, "capability": capability, "arguments": passed,
        }
        try:
            completed = subprocess.run(
                [str(self.executable), "request", "--workspace", str(self.workspace),
                 "--source-workspace", str(self.source_workspace), "--run-id", self.run_id],
                input=json.dumps(request, ensure_ascii=False, separators=(",", ":")) + "\n",
                text=True, capture_output=True, timeout=self.timeout_seconds,
                shell=False, check=False, env=self.environment,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError("PyPSA sector authority process could not complete") from exc
        self.last_diagnostics = completed.stderr
        lines = completed.stdout.splitlines()
        if len(lines) != 1:
            raise RuntimeError("PyPSA sector authority returned an invalid stdout protocol")
        try:
            response = json.loads(lines[0])
        except json.JSONDecodeError as exc:
            raise RuntimeError("PyPSA sector authority returned non-JSON stdout") from exc
        if (
            not isinstance(response, dict)
            or response.get("protocol") != "pypsa-sector-capability"
            or response.get("protocol_version") != "1.0"
            or response.get("request_id") != request_id
        ):
            raise RuntimeError("PyPSA sector response does not match its request")
        if response.get("ok") is not True:
            error = response.get("error")
            if completed.returncode == 0 and isinstance(error, dict):
                raise ValueError(str(error.get("message", "PyPSA sector failed")))
            raise RuntimeError("PyPSA sector authority failed")
        if completed.returncode != 0 or not isinstance(response.get("result"), dict):
            raise RuntimeError("PyPSA sector authority returned an invalid success")
        return response["result"]


@dataclass(slots=True)
class PreparedSectorEndpoint:
    executor: SectorExecutor
    metadata: Mapping[str, object]
    closed: bool = False

    def close(self) -> None:
        self.closed = True


class SectorProvisioner:
    def __init__(self, source_binding_id: str, *, executable: Path | None = None) -> None:
        self.source_binding_id = source_binding_id
        self.executable = executable

    def prepare(
        self, *, binding: DomainBinding, workspace: Path, credentials: CredentialLease
    ) -> PreparedSectorEndpoint:
        if credentials.scope_id != binding.credential_scope.scope_id or credentials.credentials:
            raise ValueError("PyPSA sector requires an empty, matching credential lease")
        root = Path(workspace)
        if root.is_symlink() or root.name == self.source_binding_id or not (root.parent / self.source_binding_id).is_dir():
            raise ValueError("PyPSA sector source binding is unavailable")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        bin_dir = root / "bin"
        bin_dir.mkdir(mode=0o700)
        target = bin_dir / _EXECUTABLE
        source = self.executable or Path(sys.executable).parent / _EXECUTABLE
        if not source.exists() and self.executable is None:
            found = shutil.which(_EXECUTABLE)
            if found is None:
                raise ValueError("installed pypsasectorctl is unavailable")
            source = Path(found)
        if source.is_symlink() or not source.is_file() or not os.access(source, os.X_OK):
            raise ValueError("installed pypsasectorctl is invalid")
        source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            if not stat.S_ISREG(os.fstat(source_fd).st_mode):
                raise ValueError("installed pypsasectorctl is invalid")
            target_fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o700)
            try:
                while chunk := os.read(source_fd, 64 * 1024):
                    pending = memoryview(chunk)
                    while pending:
                        count = os.write(target_fd, pending)
                        if count <= 0:
                            raise OSError("pypsasectorctl copy made no progress")
                        pending = pending[count:]
                os.fchmod(target_fd, 0o700)
            finally:
                os.close(target_fd)
        finally:
            os.close(source_fd)
        executor = SectorExecutor(
            executable=target, workspace=root, source_binding_id=self.source_binding_id,
        )
        return PreparedSectorEndpoint(executor, {
            "binding_id": binding.binding_id, "executable": _EXECUTABLE,
            "executable_args": (
                "request", "--workspace", str(root), "--source-workspace",
                str(executor.source_workspace), "--run-id", executor.run_id,
            ),
            "search_path": (str(bin_dir),), "timeout_seconds": executor.timeout_seconds,
            "environment": executor.environment,
        })


@dataclass(frozen=True, slots=True)
class VerifiedReferenceSet:
    context: tuple[VerifiedDocument, ...] = ()
    results: tuple[VerifiedDocument, ...] = ()
    evidence: tuple[VerifiedDocument, ...] = ()


class SectorArtifactAuthority:
    authority_id = "pypsasectorctl"

    def __init__(self, workspace_root: Path, source_binding_id: str) -> None:
        self.workspace_root = Path(workspace_root)
        self.source_workspace = self.workspace_root.parent / source_binding_id
        self.run_id = self.workspace_root.parent.parent.name

    def admit_handoff(self, receipt: ReferenceHandoffReceipt, *, source_workspace: Path) -> None:
        if (
            receipt.run_id != self.run_id
            or receipt.target_binding_id != self.workspace_root.name
            or receipt.source_binding_id != self.source_workspace.name
            or Path(source_workspace) != self.source_workspace
            or receipt.reference_kind != "model"
            or receipt.purpose != "sector"
            or receipt.capability_family != "sector"
            or receipt.authority_id != "pypsamodelctl"
        ):
            raise ValueError("PyPSA sector handoff does not match this binding")
        document = verify_model(self.source_workspace, self.run_id, receipt.reference)
        if receipt.revision_digest != document.reference.removeprefix("pypsa-model:sha256:"):
            raise ValueError("PyPSA sector source revision differs")

    def verify_result(self, reference: str) -> VerifiedDocument:
        return verify_sector_result(self.workspace_root, self.source_workspace, self.run_id, reference)

    def verify_evidence(self, reference: str) -> VerifiedDocument:
        return verify_sector_evidence(self.workspace_root, self.source_workspace, self.run_id, reference)

    def admit(
        self, capability: str, result: Mapping[str, object], evidence_refs: tuple[str, ...]
    ) -> VerifiedReferenceSet:
        model_ref = _reference(result.get("model_ref"), "model")
        result_ref = _reference(result.get("result_ref"), "result")
        verified = self.verify_result(result_ref)
        if verified.document.get("capability") != capability or verified.document.get("model_ref") != model_ref:
            raise ValueError("PyPSA sector result does not match the invocation")
        declared = result.get("evidence_refs")
        if not isinstance(declared, list) or tuple(declared) != evidence_refs:
            raise ValueError("PyPSA sector evidence declaration differs")
        evidence = tuple(self.verify_evidence(ref) for ref in evidence_refs)
        if not evidence or any(item.document.get("result_ref") != result_ref for item in evidence):
            raise ValueError("PyPSA sector evidence does not support the result")
        details = verified.document.get("details")
        if not isinstance(details, dict) or any(result.get(key) != value for key, value in details.items()):
            raise ValueError("PyPSA sector result differs from authority data")
        return VerifiedReferenceSet(results=(verified,), evidence=evidence)

    def audit_answer_references(
        self, claim_evidence_refs: tuple[str, ...], result_refs: tuple[str, ...]
    ) -> tuple[object, ...]:
        try:
            results = {ref: self.verify_result(ref) for ref in result_refs}
            for ref in claim_evidence_refs:
                if self.verify_evidence(ref).document.get("result_ref") not in results:
                    raise ValueError("PyPSA sector evidence does not support a declared result")
        except (ValueError, RuntimeError) as exc:
            return ({"code": "invalid_pypsa_sector_reference", "message": str(exc)},)
        return ()


@dataclass(frozen=True, slots=True)
class SectorDelta:
    model_ref: str
    result_ref: str
    evidence_refs: tuple[str, ...]

    def model_dump(self, *, mode: str = "python") -> dict[str, object]:
        del mode
        return {"model_ref": self.model_ref, "result_ref": self.result_ref, "evidence_refs": list(self.evidence_refs)}


class SectorProjector:
    projector_id = "pypsa-sector-result-v1"

    def project(self, invocation: VerifiedInvocation) -> SectorDelta:
        if invocation.projector_id != self.projector_id:
            raise ValueError("PyPSA sector projector identity differs")
        result = invocation.result
        evidence = result.get("evidence_refs")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("PyPSA sector result has no evidence")
        return SectorDelta(
            _reference(result.get("model_ref"), "model"),
            _reference(result.get("result_ref"), "result"),
            tuple(_reference(item, "evidence") for item in evidence),
        )


class SectorProjectorRegistry:
    def __init__(self) -> None:
        self._projector = SectorProjector()

    def require(self, projector_id: str) -> SectorProjector:
        if projector_id != self._projector.projector_id:
            raise LookupError("unknown PyPSA sector projector")
        return self._projector


@dataclass(frozen=True, slots=True)
class SectorContext:
    binding_id: str
    state: dict[str, object]
    admitted_refs: tuple[str, ...]

    def model_dump(self, *, mode: str = "python") -> dict[str, object]:
        del mode
        return {"binding_id": self.binding_id, "state": self.state, "admitted_refs": list(self.admitted_refs)}


class SectorStateAdapter:
    schema_id = "pypsa-sector-coupling-state/1.0"

    def _state(self, state: Mapping[str, object]) -> dict[str, Any]:
        if not state:
            return {"results": {}}
        if set(state) != {"results"} or not isinstance(state["results"], Mapping):
            raise ValueError("PyPSA sector state is invalid")
        results: dict[str, dict[str, object]] = {}
        for result_ref, raw in state["results"].items():
            _reference(result_ref, "result")
            if not isinstance(raw, Mapping) or set(raw) != {"model_ref", "evidence_refs"}:
                raise ValueError("PyPSA sector result state is invalid")
            evidence = raw["evidence_refs"]
            if not isinstance(evidence, (list, tuple)) or not evidence:
                raise ValueError("PyPSA sector evidence state is invalid")
            results[result_ref] = {
                "model_ref": _reference(raw["model_ref"], "model"),
                "evidence_refs": [_reference(item, "evidence") for item in evidence],
            }
        return {"results": results}

    def validate(self, *, binding_id: str, state: Mapping[str, object]) -> None:
        if not binding_id:
            raise ValueError("PyPSA sector binding is empty")
        self._state(state)

    def merge(self, *, binding_id: str, state: Mapping[str, object], delta: Any) -> Mapping[str, object]:
        self.validate(binding_id=binding_id, state=state)
        raw = delta.model_dump(mode="python")
        if set(raw) != {"model_ref", "result_ref", "evidence_refs"}:
            raise ValueError("PyPSA sector delta is invalid")
        parsed = self._state({"results": {raw["result_ref"]: {
            "model_ref": raw["model_ref"], "evidence_refs": raw["evidence_refs"],
        }}})
        updated = self._state(state)
        result_ref = raw["result_ref"]
        record = parsed["results"][result_ref]
        if result_ref in updated["results"] and updated["results"][result_ref] != record:
            raise ValueError("PyPSA sector result state conflicts")
        updated["results"][result_ref] = record
        return updated

    def build_context(self, *, binding_id: str, state: Mapping[str, object]) -> SectorContext:
        parsed = self._state(state)
        refs = set(parsed["results"])
        for record in parsed["results"].values():
            refs.add(record["model_ref"])
            refs.update(record["evidence_refs"])
        return SectorContext(binding_id, parsed, tuple(sorted(refs)))


class SectorAnswerEvidencePolicy:
    def validate_claim(self, claim: AnswerClaim) -> None:
        if claim.category not in {"sector", "observation", "evidence", "offline_information"}:
            raise ValueError("PyPSA sector claim category is unsupported")
        for ref in claim.result_refs:
            _reference(ref, "result")
        for ref in claim.evidence_refs:
            _reference(ref, "evidence")
        if claim.category != "offline_information" and not (claim.result_refs or claim.evidence_refs):
            raise ValueError("PyPSA sector claim has no authority lineage")
        if claim.category == "offline_information" and (claim.result_refs or claim.evidence_refs):
            raise ValueError("offline sector information cannot carry authority references")

    def validate_submission(self, submission: AnswerSubmission) -> None:
        for ref in submission.result_refs:
            _reference(ref, "result")
        for ref in submission.claim_evidence_refs:
            _reference(ref, "evidence")


class SectorAnswerAdmissionPolicy:
    def __init__(self, authority: object) -> None:
        self.authority = authority

    def admit(self, request: AnswerAdmissionInput) -> AnswerAdmissionDecision:
        if request.result_refs and request.evidence_refs:
            return AnswerAdmissionDecision(
                "authority_backed", "lineage_verified", request.answer_output,
                ("current_run_sector_lineage_verified",),
            )
        return AnswerAdmissionDecision("limited", "limited", request.answer_output, ("no_current_run_sector_result",))


class SectorOutputContract:
    schema_id = "pypsa-sector-coupling-output/1.0"

    def build(
        self, *, binding_id: str, context: DomainContextView,
        committed_answers: tuple[CommittedAnswer, ...],
    ) -> Mapping[str, object]:
        del committed_answers
        dumped = context.model_dump(mode="json")
        if dumped.get("binding_id") != binding_id:
            raise ValueError("PyPSA sector output binding differs")
        state = dumped.get("state")
        if not isinstance(state, Mapping):
            raise ValueError("PyPSA sector output state is invalid")
        parsed = SectorStateAdapter()._state(state)
        return {"result_refs": sorted(parsed["results"])}

    def validate(self, payload: Mapping[str, object]) -> None:
        if set(payload) != {"result_refs"} or not isinstance(payload["result_refs"], (list, tuple)):
            raise ValueError("PyPSA sector output is invalid")
        for ref in payload["result_refs"]:
            _reference(ref, "result")


class SectorPresentationProvider:
    def render_context(self, context: object) -> Mapping[str, object]:
        dump = getattr(context, "model_dump", None)
        raw = dump(mode="json") if callable(dump) else context
        if not isinstance(raw, Mapping):
            raise ValueError("PyPSA sector context is invalid")
        if "domains" in raw:
            domains = raw["domains"]
            if not isinstance(domains, Mapping):
                raise ValueError("PyPSA sector domains are invalid")
            matches = [
                (key, value) for key, value in domains.items()
                if isinstance(value, Mapping) and value.get("schema_id") == SectorStateAdapter.schema_id
            ]
            if len(matches) != 1:
                raise ValueError("PyPSA sector state envelope is ambiguous")
            binding_id, envelope = matches[0]
            state = envelope.get("state")
        else:
            binding_id, state = raw.get("binding_id"), raw.get("state")
        if not isinstance(binding_id, str) or not isinstance(state, Mapping):
            raise ValueError("PyPSA sector state is unavailable")
        parsed = SectorStateAdapter()._state(state)
        return {"binding_id": binding_id, "result_count": len(parsed["results"])}

    def render_report(self, context: object) -> str:
        view = self.render_context(context)
        return f"## PyPSA Sector Coupling\n\nAdmitted results: {view['result_count']}\n"


class SectorPolicyProvider:
    def __init__(self) -> None:
        self._digest = hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest()

    def load(self) -> str:
        raw = POLICY_PATH.read_bytes()
        if hashlib.sha256(raw).hexdigest() != self._digest:
            raise ValueError("PyPSA sector policy resource changed")
        return raw.decode("utf-8")


class SectorGuideProvider:
    def __init__(self) -> None:
        self._path = GUIDE_ROOT / "SKILL.md"
        self._digest = hashlib.sha256(self._path.read_bytes()).hexdigest()

    def open(self, resource_id: str) -> Mapping[str, object]:
        if resource_id != "overview":
            raise GuideNotFound(resource_id)
        raw = self._path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != self._digest:
            raise ValueError("PyPSA sector guide resource changed")
        return {"resource_id": "overview", "title": "PyPSA Sector Coupling", "sha256": self._digest, "text": raw.decode("utf-8")}

    def load(self) -> tuple[Mapping[str, object], ...]:
        return ({key: value for key, value in self.open("overview").items() if key != "text"},)


class SectorAcceptanceProfile:
    def offline_cases(self) -> tuple[object, ...]:
        return ("pypsa-sector-profile",)

    def scripted_cases(self) -> tuple[object, ...]:
        return ("pypsa-sector-current-run",)

    def provider_cases(self) -> tuple[object, ...]:
        return ()


def build_pypsa_sector_coupling_profile(*, source_binding_id: str) -> DomainRuntimeProfile:
    if not source_binding_id or "/" in source_binding_id or source_binding_id in {".", ".."}:
        raise ValueError("PyPSA sector source binding ID is invalid")
    manifest = DomainManifest(
        domain_id="pypsa-sector-coupling", version="0.1.0",
        display_name="PyPSA Sector Coupling",
        protocol="pypsa-sector-capability", protocol_version="1.0",
        executable_name="pypsasectorctl", tool_name_prefix="pypsa_sector_",
        authority_id="pypsasectorctl", capability_contract_root=CONTRACT_ROOT,
        system_policy_path=POLICY_PATH, guide_root=GUIDE_ROOT,
    )
    return DomainRuntimeProfile(
        manifest=manifest,
        contract_source=FilesystemCapabilityContractSource(CONTRACT_ROOT),
        executor_factory=lambda executable, workspace, timeout: SectorExecutor(
            executable=executable, workspace=workspace,
            source_binding_id=source_binding_id, timeout_seconds=timeout,
        ),
        projector_registry=SectorProjectorRegistry(),
        authority_factory=lambda workspace: SectorArtifactAuthority(workspace, source_binding_id),
        answer_admission_policy_factory=SectorAnswerAdmissionPolicy,
        answer_admission_policy_version="answer-admission/1.0",
        answer_admission_capabilities=frozenset({"authority_backed", "limited"}),
        tool_description_builder=describe_tool_document,
        provisioner=SectorProvisioner(source_binding_id),
        state_adapter=SectorStateAdapter(),
        answer_policy=SectorAnswerEvidencePolicy(),
        policy_provider=SectorPolicyProvider(),
        guide_provider=SectorGuideProvider(),
        presentation_provider=SectorPresentationProvider(),
        output_contract=SectorOutputContract(),
        acceptance_profile=SectorAcceptanceProfile(),
    )
