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
from typing import Any
from urllib.request import urlopen

from .federated_catalog import FederatedThreadCatalog, build_catalog_from_documents
from .harness import HarnessRuntime
from .hosted import run_hosted_api
from .thread_application import ThreadApplicationAssembly


_MAX_EXPORT_BYTES = 512 * 1024
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


def _run_exporter(root: Path, family: str, command: tuple[str, ...]) -> dict[str, Any]:
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
            process.communicate(timeout=30)
            output.seek(0)
            raw_stdout = output.read(_MAX_EXPORT_BYTES + 1)
            returncode = process.returncode
    except (OSError, subprocess.SubprocessError) as error:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        raise RuntimeError(f"{family} catalog exporter failed") from error
    if len(raw_stdout) > _MAX_EXPORT_BYTES:
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
    return build_catalog_from_documents(
        documents, default_model_id=default_model_id,
        expected_families=tuple(family for family, _ in _EXPORTERS),
    )


def _available_families() -> frozenset[str] | None:
    """Probe explicitly configured family-worker health endpoints."""

    configured = os.environ.get("CAPSTONE_FAMILY_HEALTH_URLS", "")
    if not configured.strip():
        return None
    available: set[str] = set()
    for entry in configured.split(","):
        family, separator, url = entry.partition("=")
        if not separator or not family or not url:
            raise RuntimeError("CAPSTONE_FAMILY_HEALTH_URLS is invalid")
        try:
            with urlopen(url.rstrip("/") + "/health", timeout=2) as response:
                if response.status == 200:
                    available.add(family)
        except OSError:
            continue
    return frozenset(available)


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
        available_families=_available_families(),
    )


def main() -> int:
    return run_hosted_api(build_federated_thread_application)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "build_federated_thread_application", "build_federated_thread_catalog",
    "load_federated_catalog_documents", "main",
]
