from __future__ import annotations

from collections.abc import Mapping

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
