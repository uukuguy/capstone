"""Finite M11 scenarios using the hosted prepared Authority context."""
from __future__ import annotations

from collections.abc import Mapping
from threading import RLock

from capstone_agent.kernel_capability_preparation import PreparedKernelApplicationProfile
from capstone_agent.kernel_pi_session import PreparedKernelSessionBuilder
from capstone_agent.model_capability_context import PreparedModelCapabilityContext
from capstone_agent.thread_service import AttemptClaim

from .scripted_session import _ScriptedPiSession

INSTRUCTIONS = {
    "pandapower": ("验证当前 IEEE-39 模型的交流潮流。", "复用当前 IEEE-39 Context 再次验证交流潮流。"),
    "pypsa": ("验证当前区域六母线模型的固定容量调度。", "复用当前区域六母线 Context 再次验证固定容量调度。"),
}
MODELS = {"pandapower": "ieee39", "pypsa": "regional-six-bus"}


class M11Session(_ScriptedPiSession):
    _event_prefix = "m11"

    def _build_instructions(self) -> tuple[tuple[str, tuple[Mapping[str, object], ...]], ...]:
        step: Mapping[str, object] = (
            {"capability": "analysis.powerflow.ac.run",
             "arguments": {"context_ref": "$context_ref", "algorithm": "nr"}}
            if self._family == "pandapower" else {"capability": "operations.dispatch"}
        )
        steps = ({"capability": "model.validate"}, step) if self._family == "pypsa" else (step,)
        return tuple((instruction, steps) for instruction in INSTRUCTIONS[self._family])


def build_m11_session_builder(family: str) -> PreparedKernelSessionBuilder:
    if family not in MODELS:
        raise ValueError("M11 family is not registered")
    states: dict[tuple[str, str, str], dict[str, object]] = {}
    lock = RLock()

    def build(claim: AttemptClaim, context: PreparedModelCapabilityContext,
              profiles: tuple[PreparedKernelApplicationProfile, ...]) -> M11Session:
        model = claim.model_context
        if (len(profiles) != 1 or context.closed or profiles[0].closed
                or context.thread_id != claim.thread_id or context.run_id != claim.run_id
                or context.model_context != model
                or model.implementation_family != family or model.model_id != MODELS[family]
                or (claim.turn_plan is not None and claim.turn_plan.route == "ordinary")):
            raise ValueError("M11 prepared model identity is invalid")
        binding = profiles[0].model_binding
        if (binding.model_id != model.model_id or binding.model_revision != model.model_revision
                or binding.implementation_family != family):
            raise ValueError("M11 Authority binding does not match the model")
        key = (claim.run_id, claim.model_context_id, claim.selection_revision)
        identity = (claim.thread_id, model, binding)
        with lock:
            state = states.get(key)
            if state is None:
                if len(states) >= 64:
                    raise ValueError("M11 validation context capacity reached")
                state = {"identity": identity, "context_ref": binding.context_ref,
                         "model_ref": binding.context_ref}
                states[key] = state
            elif state["identity"] != identity:
                raise ValueError("M11 retained context identity changed")
            return M11Session(claim, profiles, family=family, state=state)

    return build
