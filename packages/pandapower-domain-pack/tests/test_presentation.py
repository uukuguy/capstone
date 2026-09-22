from __future__ import annotations

from collections.abc import Mapping

from capability_agent.application.reporting import GenericReportShell
from pandapower_domain.presentation import PandapowerPresentationProvider


class _OpaqueFrame:
    def __init__(self) -> None:
        self.raw = object()

    def model_dump(self, *, mode: str = "python") -> dict[str, object]:
        return {
            "model": {"model_id": "case9", "counts": {"bus": 9}},
            "scenarios": [{"scenario_ref": "scenario:1", "status": "safe"}],
            "calculations": [{"result_ref": "result:1", "status": "converged"}],
            "raw": self.raw,
        }


def test_presenter_renders_bounded_summaries_without_raw_simulator_objects() -> None:
    provider = PandapowerPresentationProvider()

    context = provider.render_context(_OpaqueFrame())
    report = provider.render_report(_OpaqueFrame())

    model = context["model"]
    scenarios = context["scenarios"]
    calculations = context["calculations"]
    assert isinstance(model, Mapping)
    assert isinstance(scenarios, list) and scenarios
    assert isinstance(calculations, list) and calculations
    assert isinstance(scenarios[0], Mapping)
    assert isinstance(calculations[0], Mapping)
    assert model["model_id"] == "case9"
    assert scenarios[0]["status"] == "safe"
    assert calculations[0]["status"] == "converged"
    assert "<object" not in repr(context)
    assert "case9" in report
    assert "raw" not in report


def test_presenter_derives_bounded_loss_fact_card_from_projected_calculation() -> None:
    result_ref = "result:sha256:" + "1" * 64
    evidence_ref = "evidence:sha256:" + "2" * 64
    context_ref = "context:sha256:" + "3" * 64
    revision_ref = "revision:sha256:" + "4" * 64
    frame = {
        "binding_id": "grid",
        "state": {
            "model": {
                "model_id": "case9",
                "context_ref": context_ref,
                "revision_ref": revision_ref,
            },
            "calculations": {
                result_ref: {
                    "result_ref": result_ref,
                    "evidence_refs": [evidence_ref],
                    "context_ref": context_ref,
                    "revision_ref": revision_ref,
                    "producer_capability": "analysis.powerflow.ac.run",
                    "status": "converged",
                    "summary": {"total_active_loss": {"value": 1.25, "unit": "MW"}},
                }
            },
        },
    }
    provider = PandapowerPresentationProvider()

    context = provider.render_context(frame)
    card, = context["fact_cards"]
    assert card == {
        "metric": "total_active_loss",
        "value": 1.25,
        "unit": "MW",
        "model_id": "case9",
        "context_ref": context_ref,
        "revision_ref": revision_ref,
        "result_ref": result_ref,
        "evidence_refs": [evidence_ref],
    }
    report = provider.render_report(frame)
    assert "Total active loss: 1.25 MW" in report
    assert result_ref in report
    assert evidence_ref in report
    application_report = GenericReportShell().render(
        questions=("What is the active loss?",),
        answers=("The calculation completed.",),
        context=frame,
        presentation=provider,
    )
    assert "## Domain summary" in application_report
    assert "Total active loss: 1.25 MW" in application_report
    frame["state"]["calculations"][result_ref]["status"] = "failed"
    assert provider.render_context(frame)["fact_cards"] == []


def test_presenter_omits_loss_fact_without_valid_value_unit_and_lineage() -> None:
    provider = PandapowerPresentationProvider()
    frame = {
        "state": {
            "model": {"model_id": "case9"},
            "calculations": [{
                "result_ref": "result:sha256:" + "1" * 64,
                "evidence_refs": [],
                "context_ref": "context:sha256:" + "3" * 64,
                "revision_ref": "revision:sha256:" + "4" * 64,
                "producer_capability": "analysis.powerflow.ac.run",
                "status": "converged",
                "summary": {"total_active_loss": {"value": 1.25, "unit": "MWh"}},
            }],
        }
    }

    assert provider.render_context(frame)["fact_cards"] == []
    assert "Total active loss" not in provider.render_report(frame)


def test_presenter_does_not_label_a_previous_context_result_as_current_model() -> None:
    provider = PandapowerPresentationProvider()
    frame = {
        "state": {
            "model": {
                "model_id": "case9",
                "context_ref": "context:sha256:" + "9" * 64,
                "revision_ref": "revision:sha256:" + "8" * 64,
            },
            "calculations": [{
                "result_ref": "result:sha256:" + "1" * 64,
                "evidence_refs": ["evidence:sha256:" + "2" * 64],
                "context_ref": "context:sha256:" + "3" * 64,
                "revision_ref": "revision:sha256:" + "4" * 64,
                "producer_capability": "analysis.powerflow.ac.run",
                "status": "converged",
                "summary": {"total_active_loss": {"value": 1.25, "unit": "MW"}},
            }],
        }
    }

    assert provider.render_context(frame)["fact_cards"] == []
    assert "Total active loss" not in provider.render_report(frame)
