from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from capability_agent.application import AgentApplication
from capability_agent.application.errors import ApplicationConfigurationError
from capability_agent.application.output import (
    JsonOutputRenderer,
    ValidatedDomainOutput,
)
from capability_agent.application.workspace import ApplicationWorkspace

from grid_agent.application.composition import run_generic_application
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


@dataclass
class _Controller:
    starts: list[tuple[int, str]]
    submits: list[str]

    def start(self, ordinal: int, question: str) -> SimpleNamespace:
        self.starts.append((ordinal, question))
        return SimpleNamespace(turn_id=f"run-1-t{ordinal:03d}")

    def submit(self, _handle: object, *, answer_output: str, **_kwargs: object) -> SimpleNamespace:
        self.submits.append(answer_output)
        return SimpleNamespace(
            status="success",
            answer_ref=f"answer:sha256:{'a' * 64}",
            answer_output=answer_output,
            result_refs=(),
        )


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
    controller = _Controller([], [])
    application = AgentApplication(
        profile=profile,
        prepared_application=_prepared(profile),
        provider=provider,
        workspace=workspace,
        turn_controller=controller,
        catalog=object(),
        report_shell=SimpleNamespace(render=lambda **_kwargs: "# report\n"),
        domain_output_builder=lambda **_kwargs: ValidatedDomainOutput(
            schema="pandapower-static-analysis-output/1.0",
            status="completed",
            payload={"instruction_count": 2, "completed_count": 2, "failed_count": 0},
        ),
    )

    outcome = run_generic_application(
        "pandapower-static-analysis",
        ("question one", "question two"),
        application=application,
    )

    assert outcome.status == "completed"
    assert provider.started is True
    assert provider.stopped is True
    assert controller.starts == [(1, "question one"), (2, "question two")]
    assert outcome.result.schema == "capability-agent-output/1.0"
    assert outcome.result.core.application_id == "pandapower-static-analysis"
    assert tuple(outcome.result.domains) == ("grid",)
    assert outcome.result.domains["grid"].payload["completed_count"] == 2
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


def test_generic_entrypoint_rejects_request_for_a_different_application(
    tmp_path: Path,
) -> None:
    profile = build_pandapower_application_profile()
    workspace = ApplicationWorkspace.create(tmp_path / "runs", run_id="run-1", binding_ids=("grid",))
    application = AgentApplication(
        profile=profile,
        prepared_application=_prepared(profile),
        provider=_Provider(),
        workspace=workspace,
        turn_controller=_Controller([], []),
        catalog=object(),
        report_shell=SimpleNamespace(render=lambda **_kwargs: "# report\n"),
        domain_output_builder=lambda **_kwargs: ValidatedDomainOutput(
            schema="pandapower-static-analysis-output/1.0",
            status="completed",
            payload={"instruction_count": 0, "completed_count": 0, "failed_count": 0},
        ),
    )

    with pytest.raises(ApplicationConfigurationError, match="identity"):
        run_generic_application("other-application", (), application=application)
