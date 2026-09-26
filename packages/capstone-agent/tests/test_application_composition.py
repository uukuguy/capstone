from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from capability_agent.application.workspace import ApplicationWorkspace
from capstone_agent.application import build_application


def test_neutral_registry_and_builder_do_not_require_a_domain_package(tmp_path: Path) -> None:
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0"),
        domains=(SimpleNamespace(binding_id="fixture"),),
    )
    registry = SimpleNamespace(resolve=lambda _application_id, _version: profile)
    workspace = ApplicationWorkspace.create(tmp_path, run_id="fixture-run", binding_ids=("fixture",))
    application = build_application(
        "fixture-app", registry=registry,
        prepared_application=SimpleNamespace(bindings={"fixture": object()}),
        workspace=workspace,
        provider=SimpleNamespace(start=lambda: None, prompt=lambda *_args, **_kwargs: "ok",
                                 stop=lambda: None),
    )
    assert application.profile is profile
