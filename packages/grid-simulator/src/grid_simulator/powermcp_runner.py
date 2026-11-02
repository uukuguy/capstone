"""Authority-owned, fixed PowerMCP runtime and bounded structural findings."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import threading
from typing import Any

from jsonschema import Draft202012Validator
from grid_simulator.bindings.base import AnalysisPrerequisiteError
from grid_simulator.queries import asset_ref

# These hashes pin the operator installer contract for this adapter version.
# Changes to the versioned lock require a reviewed adapter update.
LOCK_SHA256 = "c29fd891be73e71e45219bda958b679bea01b5c2c9a250eb29730fc83feafbf4"
SCHEMA_SHA256 = "03a44521256095e1beb80f2fbd922c08edc802f6f7eaac85771b486ccfd311ef"
COVERAGE = {"bus_service_and_voltage_limits": "checked", "line_parameters_and_ratings": "checked",
            "transformer_ratings_and_impedance": "checked", "topology": "checked",
            "powerflow_convergence": "not_checked", "operating_security": "not_checked",
            "all_pandapower_input_defects": "not_checked"}
MAX_BYTES = 2 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024
MAX_FINDINGS = 2048


def content_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def private_environment(work: Path) -> dict[str, str]:
    return {"PATH": "/usr/bin:/bin", "HOME": str(work), "TMPDIR": str(work),
            "XDG_CACHE_HOME": str(work / "cache"), "MPLCONFIGDIR": str(work / "matplotlib"),
            "POWERIO_MCP_ALLOWED_ROOTS": str(work), "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1", "LANG": "C.UTF-8"}


def run_bounded(args: list[str], *, cwd: Path, timeout: float = 40) -> bytes:
    """Bound both streams and stop the full private process group on failure."""
    process = subprocess.Popen(args, cwd=cwd, env=private_environment(cwd), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    chunks: list[bytes] = []
    total = 0
    lock = threading.Lock()
    exceeded = threading.Event()

    def kill() -> None:
        # The pinned SDK starts its server in a separate POSIX session. The
        # fixed server launcher records that private kill scope before imports.
        try:
            server_pid = int((cwd / "mcp-server.pid").read_text())
            if server_pid > 1 and server_pid != os.getpid():
                os.killpg(server_pid, signal.SIGKILL)
        except (OSError, ValueError):
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def read(stream: Any, save: bool) -> None:
        nonlocal total
        while data := stream.read(8192):
            with lock:
                total += len(data)
                if total > MAX_BYTES:
                    exceeded.set()
                    kill()
                    return
                if save:
                    chunks.append(data)

    assert process.stdout is not None and process.stderr is not None
    readers = [threading.Thread(target=read, args=(process.stdout, True)),
               threading.Thread(target=read, args=(process.stderr, False))]
    for reader in readers:
        reader.start()
    try:
        process.wait(timeout=timeout)
        for reader in readers:
            reader.join(timeout=1)
        if any(reader.is_alive() for reader in readers):
            raise TimeoutError("PowerMCP descendants did not close")
        if exceeded.is_set():
            raise ValueError("PowerMCP output limit exceeded")
        if process.returncode != 0:
            raise ValueError("PowerMCP execution failed")
        return b"".join(chunks)
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError("PowerMCP execution timed out") from exc
    finally:
        kill()
        process.wait()
        for reader in readers:
            reader.join()
        process.stdout.close()
        process.stderr.close()


def _safe_file(root: Path, name: str) -> Path:
    if not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError("invalid prepared runtime path")
    path = root / name
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("prepared runtime path escaped")
    for parent in path.parents:
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError("prepared runtime path contains a link")
    return path


def prepared_runtime() -> tuple[dict[str, Any], Path]:
    """Consume the prepared plain descriptor without application/Kernel imports."""
    configured = os.environ.get("CAPSTONE_POWERMCP_MANAGED_ROOT")
    if not configured:
        raise AnalysisPrerequisiteError("PowerMCP structural audit runtime is unavailable", availability="unavailable")
    try:
        managed = Path(configured).resolve(strict=True)
        selected_id = os.environ.get("CAPSTONE_POWERMCP_INSTALL_ID")
        selected_hash = os.environ.get("CAPSTONE_POWERMCP_DESCRIPTOR_SHA256")
        pointer = ({"install_id": selected_id, "descriptor_sha256": selected_hash} if selected_id
                   else json.loads(_safe_file(managed, "current.json").read_text()))
        if not re.fullmatch(r"installs/[a-f0-9]{32}", pointer["install_id"]):
            raise ValueError("invalid install id")
        install = _safe_file(managed, pointer["install_id"])
        descriptor = json.loads(_safe_file(install, "prepared-mcp.json").read_text())
        if content_hash(descriptor) != pointer["descriptor_sha256"]:
            raise ValueError("prepared descriptor changed")
        schema_bytes = _safe_file(install, "descriptor-schema.json").read_bytes()
        if hashlib.sha256(schema_bytes).hexdigest() != SCHEMA_SHA256:
            raise ValueError("prepared descriptor schema changed")
        Draft202012Validator(json.loads(schema_bytes)).validate(descriptor)
        retained_lock = json.loads(_safe_file(install, "installation-lock.json").read_text())
        if content_hash(retained_lock) != LOCK_SHA256 or descriptor["lock_sha256"] != LOCK_SHA256:
            raise ValueError("prepared lock changed")
        if descriptor["descriptor_schema_sha256"] != SCHEMA_SHA256 or descriptor["install_id"] != pointer["install_id"]:
            raise ValueError("prepared installation identity changed")
        expected_sources = [{"id": s["id"], "url": s["url"], "commit": s["commit"]} for s in retained_lock["sources"]]
        expected_files = {"sources/" + s["id"] + "/" + name: digest for s in retained_lock["sources"] for name, digest in s["files"].items()}
        if (descriptor["sources"] != expected_sources or descriptor["source_files"] != expected_files
            or descriptor["dependencies"] != retained_lock["dependencies"]
            or descriptor["tool_schema_hashes"] != retained_lock["tool_schema_hashes"]):
            raise ValueError("prepared source or dependency identity changed")
        for name, digest in expected_files.items():
            if hashlib.sha256(_safe_file(install, name).read_bytes()).hexdigest() != digest:
                raise ValueError("prepared source bytes changed")
        if hashlib.sha256(_safe_file(install, "smoke.json").read_bytes()).hexdigest() != descriptor["smoke_sha256"]:
            raise ValueError("prepared smoke changed")
        for name, schema in descriptor["tool_schemas"].items():
            if content_hash(schema) != descriptor["tool_schema_hashes"][name]:
                raise ValueError("prepared tool schema changed")
        interpreter = install / "venv/bin/python"
        if hashlib.sha256(interpreter.resolve(strict=True).read_bytes()).hexdigest() != descriptor["runtime_identity"]["base_interpreter_sha256"]:
            raise ValueError("prepared interpreter changed")
        # This separate sanitized process tests actual imports and topology. The
        # MCP SDK cannot merge provider variables from the Authority parent.
        with tempfile.TemporaryDirectory(prefix="grid-mcp-ready-") as temporary:
            actual = json.loads(run_bounded([str(interpreter), "-I", "-B", str(Path(__file__).with_name("powermcp_sidecar.py")),
                                            "--inspect"], cwd=Path(temporary), timeout=15))
        if actual["dependencies"] != descriptor["dependencies"] or actual["runtime_identity"] != descriptor["runtime_identity"]:
            raise ValueError("prepared runtime changed")
        if actual["topology"] != "checked":
            raise ValueError("topology check unavailable")
        return descriptor, install
    except Exception as exc:
        raise AnalysisPrerequisiteError("PowerMCP prepared runtime verification failed", availability="unavailable") from exc


def availability() -> dict[str, Any]:
    try:
        descriptor, _ = prepared_runtime()
        return {"status": "available", "descriptor_sha256": content_hash(descriptor), "coverage": COVERAGE}
    except AnalysisPrerequisiteError:
        return {"status": "unavailable", "reason": "verified PowerMCP runtime is required"}


def invoke_snapshot(descriptor: dict[str, Any], install: Path, snapshot_sha256: str, snapshot: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="grid-structural-audit-") as temporary:
        work = Path(temporary)
        (work / "snapshot.json").write_text(snapshot)
        (work / "descriptor.json").write_text(json.dumps(descriptor, allow_nan=False))
        raw = run_bounded([str(install / "venv/bin/python"), "-I", "-B", str(Path(__file__).with_name("powermcp_sidecar.py")),
            str(install), str(work / "snapshot.json"), str(work / "descriptor.json")], cwd=work)
        receipt = json.loads(raw)
        if receipt["provenance"]["input_sha256"] != snapshot_sha256 or receipt["coverage"] != COVERAGE:
            raise ValueError("PowerMCP snapshot identity or coverage mismatch")
        return receipt


def validate_report(report: Any, net: Any) -> list[dict[str, Any]]:
    if not isinstance(report, dict) or set(report) != {"status", "audit_status", "counts", "findings"}:
        raise ValueError("invalid PowerMCP report fields")
    if report["status"] != "success" or report["audit_status"] not in {"ok", "warning", "error"}:
        raise ValueError("PowerMCP audit did not complete")
    counts, findings = report["counts"], report["findings"]
    if not isinstance(counts, dict) or set(counts) != {"errors", "warnings", "info"} or any(type(n) is not int or n < 0 for n in counts.values()):
        raise ValueError("invalid PowerMCP counts")
    if not isinstance(findings, list) or len(findings) > MAX_FINDINGS:
        raise ValueError("PowerMCP finding limit exceeded")
    rows = []
    for item in findings:
        if not isinstance(item, dict) or set(item) != {"severity", "code", "message", "element", "index"}:
            raise ValueError("invalid PowerMCP finding fields")
        severity, code, message = item["severity"], item["code"], item["message"]
        if severity not in {"error", "warning", "info"} or not isinstance(code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code):
            raise ValueError("invalid PowerMCP finding type")
        if not isinstance(message, str) or not 1 <= len(message.encode()) <= 1024 or any(ord(c) < 32 and c not in "\n\t" for c in message):
            raise ValueError("invalid PowerMCP finding message")
        kind, index = item["element"], item["index"]
        if (kind is None) != (index is None):
            raise ValueError("invalid network-level finding")
        if kind is not None and (kind not in {"bus", "line", "trafo"} or type(index) is not int or index not in net[kind].index):
            raise ValueError("PowerMCP finding is outside the current model")
        rows.append({"severity": severity, "code": code, "message": message, "element_kind": kind,
                     "element_index": index, "subject_asset_ref": asset_ref(net["_grid_agent_revision_ref"], kind, index) if kind else None})
    actual = Counter(row["severity"] for row in rows)
    if counts != {"errors": actual["error"], "warnings": actual["warning"], "info": actual["info"]}:
        raise ValueError("PowerMCP count mismatch")
    verdict = "error" if actual["error"] else "warning" if actual["warning"] else "ok"
    if report["audit_status"] != verdict:
        raise ValueError("PowerMCP verdict mismatch")
    return rows


def audit_network(engine: Any, net: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    descriptor, install = prepared_runtime()
    snapshot = engine.serialize(net)
    if len(snapshot.encode()) > MAX_SNAPSHOT_BYTES:
        raise ValueError("PowerMCP snapshot limit exceeded")
    digest = hashlib.sha256(snapshot.encode()).hexdigest()
    receipt = invoke_snapshot(descriptor, install, digest, snapshot)
    rows = validate_report(receipt["report"], net)
    return rows, {"audit_status": receipt["report"]["audit_status"], "counts": receipt["report"]["counts"],
                  "finding_count": len(rows), "coverage": receipt["coverage"], "provenance": receipt["provenance"]}
