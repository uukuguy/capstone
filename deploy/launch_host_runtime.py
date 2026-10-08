"""Start the same versioned workbench runtime in local and cloud development."""
from __future__ import annotations

import hashlib
import json
import os
import platform
from pathlib import Path
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen


class RuntimeContractError(ValueError):
    """A safe configuration key; never contains an environment value."""


def select_runtime(root: Path, environment: dict[str, str], command: str):
    contract = json.loads((root / "configs/runtime/host-runtime-v1.json").read_text())
    if environment.get("CAPSTONE_RUNTIME_PROFILE") != contract["profile"]:
        raise RuntimeContractError("CAPSTONE_RUNTIME_PROFILE")
    if environment.get("CAPSTONE_DEPLOYMENT_STAGE") not in contract["stages"]:
        raise RuntimeContractError("CAPSTONE_DEPLOYMENT_STAGE")
    application = environment.get("CAPSTONE_HOSTED_APPLICATION", "")
    if command == "api" and application == "capstone":
        role = "api"
    elif command == "worker" and application in {"pandapower", "pypsa"}:
        role = application
    else:
        raise RuntimeContractError("CAPSTONE_HOSTED_APPLICATION/command")
    spec = contract["roles"][role]
    selected = dict(environment)
    for key, expected in {**contract["shared_environment"], **spec["environment"]}.items():
        if key in selected and selected[key] != expected:
            raise RuntimeContractError(key)
        selected[key] = expected
    if selected.get("CAPSTONE_THREAD_VALIDATION"):
        raise RuntimeContractError("CAPSTONE_THREAD_VALIDATION")
    for key in selected:
        if key.startswith(("GRID_AGENT_LLM_", "CAPABILITY_AGENT_LLM_")) or key == "GRID_AGENT_PI_COMMAND":
            raise RuntimeContractError(key)
    provider = json.loads((root / "configs/llm-providers.json").read_text())["providers"][selected["CAPSTONE_PUBLIC_PROVIDER"]]
    credential_name = provider["auth"]["default_env"]
    if role != "api":
        value = selected.get(credential_name, "").strip()
        if not value or value.startswith(("replace-", "<")):
            raise RuntimeContractError(credential_name)
        selected["CAPSTONE_THREAD_FAMILY"] = spec["family"]
    return contract, role, spec, selected


def wait_for_workers(contract, environment, *, probe=None, clock=time.monotonic, sleep=time.sleep):
    endpoints = {}
    for entry in environment.get("CAPSTONE_FAMILY_HEALTH_URLS", "").split(","):
        family, separator, origin = entry.partition("=")
        if not separator or family in endpoints or not origin.startswith(("http://", "https://")):
            raise RuntimeContractError("CAPSTONE_FAMILY_HEALTH_URLS")
        endpoints[family] = origin.rstrip("/") + "/health"
    settings = contract["startup"]
    if set(endpoints) != set(settings["required_families"]):
        raise RuntimeContractError("CAPSTONE_FAMILY_HEALTH_URLS")

    def http_probe(url):
        try:
            with urlopen(url, timeout=settings["probe_timeout_seconds"]) as response:
                return response.status == 200
        except OSError:
            return False

    probe = probe or http_probe
    deadline = clock() + settings["timeout_seconds"]
    with ThreadPoolExecutor(max_workers=len(endpoints)) as pool:
        while True:
            # Submit every wake before waiting: a cold first family must not
            # postpone starting the other family.
            checks = [pool.submit(probe, endpoints[family]) for family in settings['required_families']]
            ready = [check.result() for check in checks]
            if all(ready):
                return
            if clock() >= deadline:
                raise RuntimeContractError("family worker startup deadline")
            sleep(settings["retry_seconds"])


def artifact_identity(root: Path, model_dir: Path, *, include_catalog: bool = True):
    """Hash installed logical sources, locks, package versions and model assets."""
    entries = {}

    def digest(path):
        result = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                result.update(chunk)
        return result.hexdigest()

    for parent in [root / "configs", *(root / "packages").glob("*/src")]:
        for path in parent.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix in {".py", ".mjs", ".js", ".json", ".md", ".patch"}:
                entries[str(path.relative_to(root))] = digest(path)
    for path in [root / "Dockerfile", root / "deploy/entrypoint.sh", root / "deploy/launch_host_runtime.py",
                 root / 'deploy/bake_catalog_snapshot.py',
                 *(root / "packages").glob("*/uv.lock"), *(root / "packages").glob("*/pyproject.toml"),
                 *(root / "packages").glob("*/package-lock.json")]:
        entries[str(path.relative_to(root))] = digest(path)
    versions = {}
    for metadata in (root / "packages").glob("*/.venv/lib/python*/site-packages/*.dist-info/METADATA"):
        fields = {}
        for line in metadata.read_text().splitlines():
            if line.startswith(("Name: ", "Version: ")):
                key, value = line.split(": ", 1)
                fields[key] = value
            if not line:
                break
        versions[str(metadata.relative_to(root)).split("/.venv/")[0] + ":" + fields["Name"]] = fields["Version"]
    assets = sorted(model_dir.glob("*.nc"))
    if len(assets) != 6:
        raise RuntimeContractError("pinned PyPSA model assets")
    for path in assets:
        entries["model-assets/" + path.name] = digest(path)
    snapshot_path = root / '.capstone-agent/federated-catalog.json'
    if include_catalog and snapshot_path.exists():
        snapshot = json.loads(snapshot_path.read_bytes())
        # Exclude the declared identity to avoid a circular hash, but bind all
        # installed metadata. Any payload change changes the runtime receipt.
        metadata = {'schema': snapshot['schema'], 'documents': snapshot['documents']}
        entries['installed-authority-catalog'] = hashlib.sha256(
            json.dumps(metadata, sort_keys=True).encode()).hexdigest()
    payload = {"files": entries, "packages": versions, "python": list(sys.version_info[:3])}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        if len(sys.argv) != 2:
            raise RuntimeContractError("startup command")
        contract, role, spec, environment = select_runtime(root, dict(os.environ), sys.argv[1])
        if role == "api":
            wait_for_workers(contract, environment)
        receipt = {
            "schema": "capstone-host-runtime-receipt/1", "profile": contract["profile"],
            "contract_sha256": hashlib.sha256((root / "configs/runtime/host-runtime-v1.json").read_bytes()).hexdigest(),
            "artifact_sha256": artifact_identity(root, Path(environment["CAPSTONE_PYPSA_MODEL_LIBRARY_DIR"])),
            "source_artifact_sha256": artifact_identity(root, Path(environment["CAPSTONE_PYPSA_MODEL_LIBRARY_DIR"]), include_catalog=False),
            "architecture": platform.machine(),
            "role": role, "application": spec["application"],
            "stage": environment["CAPSTONE_DEPLOYMENT_STAGE"], "dependencies_ready": True,
            "provider_configured": role != "api",
        }
        environment['CAPSTONE_RUNTIME_ARTIFACT_SHA256'] = receipt['artifact_sha256']
        directory = root / ".capstone-agent"
        directory.mkdir(exist_ok=True)
        path = directory / "host-runtime.json"
        path.write_text(json.dumps(receipt, sort_keys=True))
        path.chmod(0o600)
        print("Host runtime contract accepted: " + role + " " + receipt["contract_sha256"], file=sys.stderr, flush=True)
        executable = str(root / "packages" / spec["project"] / ".venv/bin/python")
        os.execve(executable, [executable, "-m", spec["module"]], environment)
    except (OSError, ValueError, KeyError) as error:
        # Never log environment values, credentials or exception contents.
        key = str(error) if isinstance(error, RuntimeContractError) else "runtime files"
        print("Host runtime contract rejected: " + key, file=sys.stderr)
        return 78
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
