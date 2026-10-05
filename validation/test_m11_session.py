from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from validation.thread.provider_free_host import ProviderFreeThreadHost


def test_m11_builder_rejects_identity_drift_and_capacity(monkeypatch):
    from types import SimpleNamespace as NS
    import validation.thread.m11_session as module

    monkeypatch.setattr(module, "M11Session", lambda claim, profiles, **kwargs: kwargs["state"])
    builder = module.build_m11_session_builder("pypsa")

    def inputs(index):
        model = NS(id=f"ctx_{index}", model_id="regional-six-bus", model_revision="revision:one",
                   implementation_family="pypsa")
        claim = NS(thread_id="thr_one", run_id="run_one", model_context_id=model.id,
                   selection_revision="sel_0", model_context=model, turn_plan=None)
        context = NS(closed=False, thread_id=claim.thread_id, run_id=claim.run_id, model_context=model)
        binding = NS(model_id=model.model_id, model_revision=model.model_revision,
                     implementation_family="pypsa", context_ref="model:one")
        return claim, context, (NS(closed=False, model_binding=binding),)

    args = inputs(0)
    first = builder(*args)
    assert builder(*args) is first
    args[1].run_id = "run_foreign"
    with pytest.raises(ValueError, match="identity"):
        builder(*args)
    for index in range(1, 64):
        builder(*inputs(index))
    with pytest.raises(ValueError, match="capacity"):
        builder(*inputs(64))
    args = inputs(0)
    args[2][0].model_binding.context_ref = "model:changed"
    with pytest.raises(ValueError, match="identity"):
        builder(*args)


@pytest.mark.parametrize("family,model", [("pandapower", "ieee39"), ("pypsa", "regional-six-bus")])
def test_m11_uses_real_hosted_authority_without_provider(monkeypatch, tmp_path: Path, family, model):
    pytest.importorskip("grid_simulator" if family == "pandapower" else "pypsa_model_authority")
    from validation.thread.m11_session import INSTRUCTIONS
    from validation.thread.m11_session import M11Session
    original_admit = M11Session.admit_attempt

    def check_foreign_reference(self, claim, answer, result_refs, evidence_refs, tool_events):
        with pytest.raises(ValueError, match="provenance owner"):
            self._admission(claim, answer, (*result_refs, "result:sha256:" + "f" * 64),
                            evidence_refs, tool_events)
        return original_admit(self, claim, answer, result_refs, evidence_refs, tool_events)

    monkeypatch.setattr(M11Session, "admit_attempt", check_foreign_reference)
    hosted = importlib.import_module("grid_agent.hosted" if family == "pandapower" else "pypsa_agent.hosted")
    monkeypatch.setenv("CAPSTONE_THREAD_VALIDATION", "m11")
    monkeypatch.setenv("CAPSTONE_DEPLOYMENT_STAGE", "cloud-development")
    monkeypatch.setenv("CAPSTONE_RUNS_ROOT", str(tmp_path.resolve()))
    monkeypatch.setenv("CAPSTONE_PUBLIC_PROVIDER", "must-not-run")

    def forbidden(*args, **kwargs):
        raise AssertionError("Provider construction must not run")

    for name in ("resolve_llm", "build_runtime_host", "PreparedKernelPiRpcSessionBuilder"):
        monkeypatch.setattr(hosted, name, forbidden)
    factory = getattr(hosted, f"build_registered_{family}_thread_application")
    monkeypatch.setattr(ProviderFreeThreadHost, "_build_assembly", lambda self: factory())
    app_id = "pandapower-static-analysis" if family == "pandapower" else "pypsa-business-cases"
    with ProviderFreeThreadHost(app_id, tmp_path) as session:
        initial = session.create(model)
        for instruction in INSTRUCTIONS[family]:
            assert session.command("send_professional", {"text": instruction}).status == "accepted"
            snapshot = session.snapshot()
            assert snapshot.active_model_context.id == initial.active_model_context.id
            events = session.events().events
            assert events[-1].event_type != "attempt_failed", [event.to_document() for event in events]
            assert any(event.event_type == "attempt_completed" for event in events)
            assert snapshot.result_projections
        if family == "pypsa":
            assert any(event.event_type == "network_diagram" for event in events)
            assert any(event.event_type == "network_layer" for event in events)
        exhausted = session.command("send_professional", {"text": INSTRUCTIONS[family][0]})
        assert any(event.event_type == "attempt_failed" and event.attempt_id == exhausted.target["attempt_id"]
                   for event in session.events().events)
        receipt = session.command("reopen_model_context", {"model_id": model, "reason": "M11 fresh context"})
        assert receipt.status == "accepted"
        assert session.snapshot().pending_model_switch is not None
        session.command("send_professional", {"text": INSTRUCTIONS[family][0]})
        assert session.snapshot().active_model_context.id != initial.active_model_context.id
        assert session.snapshot().result_projections
        session.command("send_professional", {"text": "arbitrary validation instruction"})
        assert any(event.event_type == "attempt_failed" for event in session.events().events)
