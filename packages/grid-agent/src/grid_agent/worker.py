"""Pandapower application worker for the neutral Capstone session host."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from capstone_agent.worker import PreparedWorker, read_verified_reference, serve_application
from capability_agent.runtime.catalog import ProviderCatalog

from grid_agent.application.composition import build_generic_application


ROOT = Path(__file__).resolve().parents[4]
APPLICATION_ID = "pandapower-static-analysis"
CASES = frozenset({"pandapower-scripted-task", "pandapower-scripted-test"})


class _ScriptedCaseApplication:
    def __init__(self, case: dict[str, Any], observer) -> None:
        self.case = case
        self.observer = observer
        self.execution: Any = None
        self.prepared: Any = None

    def run_stream(self, request, instructions):
        from validation.run import execute_application_case

        self.case["run_id"] = request.run_id

        def progress(event: dict[str, object]) -> None:
            self.observer({"type": event.get("event", "progress"),
                           "message": event.get("message", "")})

        execution = execute_application_case(
            self.case, runs_root=ROOT / "runs" / "capstone-agent",
            instruction_source=instructions, on_semantic_event=self.observer,
            on_progress=progress,
            on_prepared=lambda prepared: setattr(self, "prepared", prepared),
        )
        self.execution = execution
        return execution.outcome


def _prepare(values: Mapping[str, object], observer) -> PreparedWorker:
    if values.get("application_id") != APPLICATION_ID:
        raise ValueError("pandapower worker application is invalid")
    run_id = values.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("pandapower worker run ID is invalid")
    mode = values.get("mode")
    if mode == "scripted-demo":
        case_id = values.get("case_id")
        if case_id not in CASES:
            raise ValueError("pandapower case is not registered")
        document = json.loads(
            (ROOT / "validation" / "application" / f"{case_id}.json").read_text(encoding="utf-8")
        )
        application = _ScriptedCaseApplication(document, observer)

        def evidence(reference: str) -> object | None:
            prepared = application.prepared
            return (
                read_verified_reference(prepared, reference)
                if prepared is not None else None
            )

        return PreparedWorker(application, run_id, evidence)
    if mode != "provider" or values.get("case_id") is not None:
        raise ValueError("pandapower worker mode is invalid")
    provider = values.get("provider")
    model = values.get("model")
    if provider is not None and not isinstance(provider, str):
        raise ValueError("Provider is invalid")
    if model is not None and not isinstance(model, str):
        raise ValueError("model is invalid")
    from grid_agent.cli.app import _generic_runtime_environment, _runtime_environment

    application = build_generic_application(
        APPLICATION_ID, provider=provider, model=model,
        provider_catalog=ProviderCatalog.load(ROOT / "configs/llm-providers.json"),
        workspace_root=ROOT / "runs" / "capstone-agent",
        run_id=run_id,
        environment=_generic_runtime_environment(_runtime_environment(ROOT)),
        semantic_event_observer=observer,
    )
    return PreparedWorker(
        application, run_id,
        lambda reference: read_verified_reference(application.prepared_application, reference),
    )


def main() -> None:
    serve_application(_prepare)


if __name__ == "__main__":
    main()
