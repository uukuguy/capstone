"""Hosted API root for one Capstone Thread over multiple model families.

The control plane reads bounded metadata from each Authority adapter through a
fixed exporter command.  It never imports pandapower or PyPSA.  Family workers
run the corresponding adapter and lease only their own implementation family.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.request import urlopen

from .federated_catalog import FederatedThreadCatalog, build_catalog_from_documents
from .harness import HarnessRuntime
from .hosted import run_hosted_api
from .thread_application import ThreadApplicationAssembly


_MAX_EXPORT_BYTES = 512 * 1024
# Exporters verify every registered model revision, including large networks.
# Keep startup bounded while allowing a cold authority under local build load.
_EXPORT_TIMEOUT_SECONDS = 120
_EXPORTERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "pandapower",
        ("uv", "run", "--no-sync", "--project", "packages/grid-agent", "python", "-m", "grid_agent.thread_catalog_export"),
    ),
    (
        "pypsa",
        ("uv", "run", "--no-sync", "--project", "packages/pypsa-agent", "python", "-m", "pypsa_agent.thread_catalog_export"),
    ),
)


def _root() -> Path:
    configured = os.environ.get("CAPSTONE_REPO_ROOT")
    return Path(configured).resolve() if configured else Path(__file__).resolve().parents[4]


def _run_exporter(root: Path, family: str, command: tuple[str, ...], *, max_bytes: int = _MAX_EXPORT_BYTES) -> dict[str, Any]:
    environment = {
        key: os.environ[key]
        for key in ("PATH", "CAPSTONE_PYPSA_MODEL_LIBRARY_DIR", "CAPSTONE_GRID_MODEL_LIBRARY_DIR")
        if key in os.environ
    }
    process: subprocess.Popen[bytes] | None = None
    try:
        with tempfile.TemporaryFile() as output:
            process = subprocess.Popen(
                list(command), cwd=root, shell=False, stdout=output,
                stderr=subprocess.PIPE, env=environment,
            )
            process.communicate(timeout=_EXPORT_TIMEOUT_SECONDS)
            output.seek(0)
            raw_stdout = output.read(max_bytes + 1)
            returncode = process.returncode
    except (OSError, subprocess.SubprocessError) as error:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        raise RuntimeError(f"{family} catalog exporter failed") from error
    if len(raw_stdout) > max_bytes:
        raise RuntimeError(f"{family} catalog export is too large")
    if returncode != 0:
        raise RuntimeError(f"{family} catalog exporter failed")
    try:
        document = json.loads(raw_stdout.decode("utf-8"))
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"{family} catalog export is not JSON") from error
    if not isinstance(document, dict):
        raise RuntimeError(f"{family} catalog export is not an object")
    return document


def load_federated_catalog_documents(root: Path | None = None) -> tuple[dict[str, Any], ...]:
    """Run the two fixed metadata exporters and return their JSON documents."""

    resolved_root = (root or _root()).resolve()
    return tuple(
        _run_exporter(resolved_root, family, command)
        for family, command in _EXPORTERS
    )


def build_federated_thread_catalog(
    root: Path | None = None, *, default_model_id: str | None = None,
) -> FederatedThreadCatalog:
    documents = load_federated_catalog_documents(root)
    catalog = build_catalog_from_documents(
        documents, default_model_id=default_model_id,
        expected_families=tuple(family for family, _ in _EXPORTERS),
    )
    def diagram(model_id: str, revision: str) -> dict[str, Any]:
        from .network_diagram import MAX_DIAGRAM_BYTES, normalize_network_diagram
        descriptor = catalog.model_catalog.resolve(model_id)
        if descriptor.model_revision != revision or not descriptor.available:
            raise ValueError("exact registered model revision is unavailable")
        command = next(command for family, command in _EXPORTERS if family == descriptor.implementation_family)
        return normalize_network_diagram(_run_exporter((root or _root()).resolve(), descriptor.implementation_family,
            (*command, "--diagram", model_id, revision), max_bytes=MAX_DIAGRAM_BYTES + 64 * 1024))
    catalog.model_catalog.set_diagram_provider(diagram)
    return catalog


def _probe_family(origin: str, *, sleep=time.sleep) -> bool:
    for attempt in range(8):
        try:
            with urlopen(origin.rstrip('/') + '/health', timeout=2) as response:
                if response.status == 200:
                    return True
        except OSError:
            pass
        if attempt < 7:
            sleep(min(0.5 * 2 ** attempt, 3))
    return False


def _available_families() -> frozenset[str] | None:
    """Probe explicitly configured family-worker health endpoints."""

    configured = os.environ.get("CAPSTONE_FAMILY_HEALTH_URLS", "")
    if not configured.strip():
        return None
    endpoints = []
    for entry in configured.split(","):
        family, separator, url = entry.partition("=")
        if not separator or not family or not url:
            raise RuntimeError("CAPSTONE_FAMILY_HEALTH_URLS is invalid")
        endpoints.append((family, url))
    # These probes run only for a caller's catalog/admission request. Cold
    # families wake together rather than extending the first-request delay.
    with ThreadPoolExecutor(max_workers=len(endpoints)) as pool:
        readiness = list(pool.map(_probe_family, [url for _, url in endpoints]))
    return frozenset(family for (family, _), ready in zip(endpoints, readiness) if ready)


def _api_only_runtime(_claim: object) -> HarnessRuntime:
    raise RuntimeError("federated API does not execute Attempts")


def build_federated_thread_application(
    root: Path | None = None,
) -> ThreadApplicationAssembly:
    catalog = build_federated_thread_catalog(root)
    return ThreadApplicationAssembly.from_composite_authority(
        catalog=catalog.model_catalog,
        runtime_factories={
            "pandapower": _api_only_runtime,
            "pypsa": _api_only_runtime,
        },
        capability_catalog=catalog.capability_catalog,
        catalog_context=catalog.to_document(),
        available_families=_available_families,
    )


def main() -> int:
    return run_hosted_api(build_federated_thread_application)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "build_federated_thread_application", "build_federated_thread_catalog",
    "load_federated_catalog_documents", "main",
]
