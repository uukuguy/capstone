from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from capability_agent.application.errors import ApplicationConfigurationError
from capability_agent.application.output import (
    JsonOutputRenderer,
)
from capability_agent.application.workspace import ApplicationWorkspace
from capability_agent.runtime.lock import PiCommand, PiRuntimeIdentity

import grid_agent.application.composition as composition_module
from grid_agent.application.composition import (
    build_generic_application,
    run_generic_application,
)
from grid_agent.application.paths import ProjectPaths
from grid_agent.application.profile import build_pandapower_application_profile


@dataclass
class _Provider:
    answers: tuple[str, ...] = ("first", "second")
    started: bool = False
    stopped: bool = False
    index: int = 0

    def start(self) -> None:
        self.started = True

    def prompt_and_wait(self, _question: str, **_kwargs: object) -> str:
        answer = self.answers[self.index]
        self.index += 1
        return answer

    def stop(self) -> None:
        self.stopped = True


class _Renderer:
    def render(self, result: object) -> str:
        return JsonOutputRenderer().render(result)  # type: ignore[arg-type]


def _prepared(profile: object) -> SimpleNamespace:
    binding = profile.domains[0]  # type: ignore[attr-defined]
    endpoint = SimpleNamespace(close=lambda: None)
    return SimpleNamespace(
        bindings={
            "grid": SimpleNamespace(
                binding=binding,
                endpoint=endpoint,
                runtime=SimpleNamespace(authority=SimpleNamespace(authority_id="gridctl")),
            )
        }
    )


def test_generic_entrypoint_renders_validated_core_and_domain_sections(
    tmp_path: Path,
) -> None:
    profile = build_pandapower_application_profile()
    workspace = ApplicationWorkspace.create(tmp_path / "runs", run_id="run-1", binding_ids=("grid",))
    provider = _Provider()
    application = build_generic_application(
        "pandapower-static-analysis",
        prepared_application=_prepared(profile),
        provider=provider,
        workspace=workspace,
        catalog=object(),
    )

    outcome = run_generic_application(
        "pandapower-static-analysis",
        ("question one", "question two"),
        application=application,
    )

    assert outcome.status == "completed", outcome.error
    assert provider.started is True
    assert provider.stopped is True
    assert outcome.result.schema == "capability-agent-output/1.0"
    assert outcome.result.core.application_id == "pandapower-static-analysis"
    assert outcome.result.core.report_ref is not None
    assert tuple(outcome.result.domains) == ("grid",)
    domain_payload = outcome.result.domains["grid"].payload
    assert domain_payload == {
        "mode": "continuous-static-analysis",
        "instruction_count": 2,
        "completed_count": 2,
        "failed_count": 0,
        "report_artifact_ref": outcome.result.core.report_ref,
    }
    assert workspace.output_path.joinpath("report.md").is_file()
    report_digest = sha256(
        workspace.output_path.joinpath("report.md").read_bytes()
    ).hexdigest()
    assert outcome.result.core.report_ref == f"artifact:sha256:{report_digest}"
    assert outcome.result.core.report_ref in workspace.root.joinpath(
        "core/context-events.jsonl"
    ).read_text(encoding="utf-8")
    assert isinstance(outcome.rendered, str)
    rendered = json.loads(outcome.rendered)
    assert set(rendered) == {"schema", "core", "domains"}
    assert set(rendered["core"]) == {
        "application_id",
        "application_version",
        "run_id",
        "status",
        "answer_refs",
        "report_ref",
        "diagnostic_refs",
    }
    assert set(rendered["domains"]["grid"]) == {
        "domain_id",
        "domain_version",
        "schema",
        "status",
        "payload",
    }
    assert rendered["core"]["report_ref"] == rendered["domains"]["grid"][
        "payload"
    ]["report_artifact_ref"]


def test_generic_entrypoint_rejects_request_for_a_different_application(
    tmp_path: Path,
) -> None:
    profile = build_pandapower_application_profile()
    workspace = ApplicationWorkspace.create(tmp_path / "runs", run_id="run-1", binding_ids=("grid",))
    application = build_generic_application(
        "pandapower-static-analysis",
        prepared_application=_prepared(profile),
        provider=_Provider(),
        workspace=workspace,
        catalog=object(),
    )

    with pytest.raises(ApplicationConfigurationError, match="identity"):
        run_generic_application("other-application", (), application=application)


def test_generic_composition_injects_product_owned_runtime_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The grid composition root supplies trusted Pi assets to the generic Kernel."""

    from capability_agent.runtime.environment import RuntimeHost
    from capability_agent.runtime.extension import ExtensionSpec

    monkeypatch.chdir(tmp_path)
    profile = build_pandapower_application_profile()
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="host-run", binding_ids=("grid",)
    )
    command = PiCommand(
        argv=("node", "/product-owned/pi.js"),
        identity=PiRuntimeIdentity(
            path=Path("/product-owned/pi.js"),
            source="fixture",
            package_version="1.0.0",
            lock_sha256="fixture-lock",
        ),
    )
    lock_calls: dict[str, Path] = {}
    locator_calls: dict[str, object] = {}

    class FakeLock:
        @classmethod
        def load(cls, path: Path) -> object:
            lock_calls["path"] = path
            return cls()

    class FakeRuntimeLocator:
        def __init__(
            self,
            runtime_dir: Path,
            environ: object,
            *,
            runtime_lock: object,
        ) -> None:
            locator_calls.update(
                runtime_dir=runtime_dir,
                environ=environ,
                runtime_lock=runtime_lock,
            )

        def resolve(self) -> PiCommand:
            return command

    class FakeExtensionLocator:
        def __init__(self, project_root: Path, *, spec: ExtensionSpec) -> None:
            locator_calls["extension_root"] = project_root
            locator_calls["extension_spec"] = spec

        def resolve(self) -> Path:
            return tmp_path / "trusted-extension.mjs"

    monkeypatch.setattr(
        composition_module,
        "_runtime_host_dependencies",
        lambda: (FakeExtensionLocator, FakeLock, FakeRuntimeLocator),
    )

    application = build_generic_application(
        "pandapower-static-analysis",
        prepared_application=_prepared(profile),
        provider_catalog=object(),
        workspace=workspace,
        environment={"PATH": "/usr/bin"},
        catalog=object(),
    )

    assert isinstance(application.runtime_host, RuntimeHost)
    assert application.runtime_host.command == command
    assert application.runtime_host.project_pi_dir == ProjectPaths.from_root(
        tmp_path
    ).pi_agent_dir
    assert application.runtime_host.extension_path == tmp_path / "trusted-extension.mjs"
    assert application.runtime_host.system_policy_path == profile.domains[0].profile.manifest.system_policy_path
    assert locator_calls["runtime_dir"] == ProjectPaths.from_root(tmp_path).pi_runtime_dir
    assert lock_calls["path"] == ProjectPaths.from_root(tmp_path).runtime_lock
    assert locator_calls["extension_root"] == tmp_path
    extension_spec = locator_calls["extension_spec"]
    assert isinstance(extension_spec, ExtensionSpec)
    assert extension_spec.package_name == "@capability-agent/pi-tools"
    assert extension_spec.package_version == "0.1.0"
    assert extension_spec.candidates == (Path("packages/pi-capability-tools"),)


def test_generic_host_resolves_domain_neutral_pi_extension() -> None:
    """Generic composition must bind the v1 runtime to generic Pi tools."""

    from capability_agent.runtime.extension import ExtensionSpec

    project_root = Path(__file__).resolve().parents[4]
    extension_locator, _lock, _runtime = composition_module._runtime_host_dependencies()

    assert extension_locator.__module__ == "capability_agent.runtime.extension"
    extension = extension_locator(
        project_root,
        spec=ExtensionSpec(
            package_name="@capability-agent/pi-tools",
            package_version="0.1.0",
            candidates=(Path("packages/pi-capability-tools"),),
        ),
    ).resolve()

    assert extension == project_root / "packages/pi-capability-tools/src/domain-tools.mjs"
    assert "pi-grid-tools" not in extension.parts
