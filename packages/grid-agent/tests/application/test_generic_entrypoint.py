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

from grid_agent.application.composition import (
    build_generic_application,
    run_generic_application,
)
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
