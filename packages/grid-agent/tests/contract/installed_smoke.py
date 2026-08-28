from __future__ import annotations

import json
import tempfile
from dataclasses import replace
from pathlib import Path

from capability_agent import DomainManifest, prepare_domain_runtime
from pandapower_domain import build_pandapower_profile


class FakeExecutor:
    def __init__(self, environment: dict[str, object]) -> None:
        self.environment = environment
        self.calls: list[tuple[str, dict[str, object]]] = []

    def invoke(
        self, capability: str, arguments: dict[str, object]
    ) -> dict[str, object]:
        self.calls.append((capability, arguments))
        if capability != "environment.describe":
            raise AssertionError(f"unexpected simulator call: {capability}")
        if arguments:
            raise AssertionError(f"unexpected environment arguments: {arguments}")
        return self.environment


def main() -> None:
    profile = build_pandapower_profile()
    profile.manifest.assert_resources_present()
    assert isinstance(profile.manifest, DomainManifest)
    assert profile.manifest.protocol == "grid-capability"
    assert profile.manifest.executable_name == "gridctl"

    capability_documents = profile.contract_source.load()
    environment = {
        "protocol": profile.manifest.protocol,
        "protocol_version": profile.manifest.protocol_version,
        "executable_capabilities": [
            {
                "id": document["id"],
                "availability": document["availability"],
                "context_effect": document["context_effect"],
            }
            for document in capability_documents
            if document["availability"] == "published"
        ],
    }
    executor = FakeExecutor(environment)
    profile = replace(
        profile,
        executor_factory=lambda executable, workspace, timeout: executor,
    )

    with tempfile.TemporaryDirectory(prefix="grid-installed-smoke-") as scratch:
        workspace = Path(scratch)
        prepared = prepare_domain_runtime(
            profile,
            executable=workspace / "bin/gridctl",
            workspace=workspace / "run",
            tool_catalog_path=workspace / "run/tool-catalog.json",
            guide_index_path=workspace / "run/guide-index.json",
        )

        catalog = json.loads(
            prepared.tool_catalog_path.read_text(encoding="utf-8")
        )
        guide_index = json.loads(
            prepared.guide_index_path.read_text(encoding="utf-8")
        )
        assert executor.calls == [("environment.describe", {})]
        assert catalog["protocol"] == "grid-tool-catalog"
        assert any(tool["name"] == "grid_environment_describe" for tool in catalog["tools"])
        assert guide_index["protocol"] == "grid-guide-index"
        assert "overview" in guide_index["resources"]

    print("installed-smoke: ok")


if __name__ == "__main__":
    main()
