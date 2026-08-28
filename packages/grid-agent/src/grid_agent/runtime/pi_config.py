from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from capability_agent.domain import DomainManifest
from grid_agent.config.models import ResolvedLLM


@dataclass(frozen=True)
class PiConfigPaths:
    settings_path: Path
    models_path: Path


class PiConfigMaterializer:
    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)

    def materialize(self, resolved: ResolvedLLM) -> PiConfigPaths:
        self.directory.mkdir(parents=True, exist_ok=True)
        os.chmod(self.directory, 0o700)
        settings_path = self.directory / "settings.json"
        models_path = self.directory / "models.json"
        timeout_ms = round(resolved.config.timeout_seconds * 1_000)
        retries = resolved.config.max_retries
        settings = {
            "httpIdleTimeoutMs": timeout_ms,
            "retry": {
                "enabled": retries > 0,
                "maxRetries": retries,
                "provider": {"timeoutMs": timeout_ms, "maxRetries": retries},
            },
        }
        settings_path.write_text(json.dumps(settings, separators=(",", ":")) + "\n", encoding="utf-8")
        is_official = resolved.config.base_url == "https://api.openai.com/v1" and not resolved.config.public_headers
        models = {} if is_official else {"providers": {resolved.config.pi_provider: {"baseUrl": resolved.config.base_url, "headers": dict(resolved.config.public_headers)}}}
        models_path.write_text(json.dumps(models, separators=(",", ":")) + "\n", encoding="utf-8")
        os.chmod(settings_path, 0o600)
        os.chmod(models_path, 0o600)
        return PiConfigPaths(settings_path=settings_path, models_path=models_path)

    def materialize_domain_runtime(
        self,
        manifest: DomainManifest,
        *,
        workspace: Path,
        tool_catalog_path: Path | None = None,
        guide_index_path: Path | None = None,
        active_turn_path: Path | None = None,
        analysis_context_view_path: Path | None = None,
        trajectory_requests_path: Path | None = None,
        trajectory_capture_state_path: Path | None = None,
        trajectory_allowed_refs_path: Path | None = None,
        trajectory_acks_path: Path | None = None,
        pi_runtime: Mapping[str, str] | None = None,
    ) -> Path:
        """Atomically materialize the fixed model-runtime transport descriptor."""

        descriptor_directory = workspace / "pi"
        descriptor_directory.mkdir(parents=True, exist_ok=True)
        os.chmod(descriptor_directory, 0o700)
        descriptor_path = descriptor_directory / "domain-runtime.json"
        runtime_descriptor: dict[str, object] = {
            **self.domain_transport_descriptor(manifest, workspace=workspace),
            "tool_catalog_path": str(
                tool_catalog_path or workspace / "tool-catalog.json"
            ),
            "guide_index_path": str(
                guide_index_path or workspace / "guide-index.json"
            ),
            "workspace_path": str(workspace),
        }
        optional_paths = {
            "active_turn_path": active_turn_path,
            "analysis_context_view_path": analysis_context_view_path,
            "trajectory_requests_path": trajectory_requests_path,
            "trajectory_capture_state_path": trajectory_capture_state_path,
            "trajectory_allowed_refs_path": trajectory_allowed_refs_path,
            "trajectory_acks_path": trajectory_acks_path,
        }
        runtime_descriptor.update(
            {
                name: str(path) if path is not None else None
                for name, path in optional_paths.items()
            }
        )
        runtime_descriptor["pi_runtime"] = (
            dict(pi_runtime) if pi_runtime is not None else None
        )
        payload = (
            json.dumps(runtime_descriptor, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{descriptor_path.name}.",
            dir=descriptor_directory,
        )
        temporary_path = Path(temporary_name)
        try:
            os.chmod(temporary_path, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            temporary_path.replace(descriptor_path)
            os.chmod(descriptor_path, 0o600)
            directory_descriptor = os.open(descriptor_directory, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if temporary_path.exists():
                temporary_path.unlink()
        return descriptor_path

    @staticmethod
    def domain_transport_descriptor(
        manifest: DomainManifest,
        *,
        workspace: Path,
    ) -> dict[str, object]:
        """Return the exact Task 7 transport API before run-state enrichment."""
        return {
            "protocol": manifest.protocol,
            "protocol_version": manifest.protocol_version,
            "executable": manifest.executable_name,
            "executable_args": ["request", "--workspace", str(workspace)],
            "tool_name_prefix": manifest.tool_name_prefix,
            "guide_tool_name": f"{manifest.tool_name_prefix}guide_open",
            "context_tool_name": f"{manifest.tool_name_prefix}analysis_context_get",
            "decision_tool_name": f"{manifest.tool_name_prefix}record_decision",
        }
