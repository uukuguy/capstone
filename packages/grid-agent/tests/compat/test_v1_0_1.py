from __future__ import annotations

import json

from capability_agent.application.output import (
    ApplicationResult,
    BindingIdentity,
    CoreRunResult,
    FrameworkOutputComposer,
    ValidatedDomainOutput,
)

from grid_agent.compat.v1_0_1 import (
    LEGACY_CORE_TOOL_ALIASES,
    V1_0_1CompatibilityAdapter,
    build_grid_v1_0_1_compatibility_adapter,
)


def _result() -> ApplicationResult:
    return FrameworkOutputComposer().compose(
        core=CoreRunResult(
            application_id="pandapower-static-analysis",
            application_version="1.0.1",
            run_id="run-1",
            status="completed",
            answer_refs=("answer:sha256:" + "a" * 64,),
            report_ref="artifact:sha256:" + "b" * 64,
            diagnostic_refs=(),
        ),
        bindings=(
            BindingIdentity(
                binding_id="grid",
                domain_id="pandapower-static-analysis",
                domain_version="1.0.1",
            ),
        ),
        domains={
            "grid": ValidatedDomainOutput(
                schema="pandapower-static-analysis-output/1.0",
                status="completed",
                payload={"completed_count": 2},
            )
        },
    )


def test_v1_0_1_adapter_projects_exactly_the_legacy_two_fields() -> None:
    adapter = build_grid_v1_0_1_compatibility_adapter()

    rendered = adapter.render(question_id="run-1", answer_output="runs/run-1/report.md")

    assert json.loads(rendered) == {
        "question_id": "run-1",
        "answer_output": "runs/run-1/report.md",
    }
    assert adapter.project_result(_result()) == {
        "question_id": "run-1",
        "answer_output": "runs/run-1/report.md",
    }


def test_compatibility_adapter_does_not_mutate_validated_application_result() -> None:
    adapter = V1_0_1CompatibilityAdapter()
    result = _result()
    before = result.model_dump(mode="json")

    adapter.project_result(result)

    assert result.model_dump(mode="json") == before
    assert "admit" not in dir(adapter)
    assert "audit_answer_references" not in dir(adapter)
    assert all(name.startswith("grid_") for name in LEGACY_CORE_TOOL_ALIASES)
