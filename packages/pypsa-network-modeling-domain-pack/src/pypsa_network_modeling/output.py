"""Pack-owned output and presentation of admitted model references."""

from __future__ import annotations

from collections.abc import Mapping

from pypsa_network_modeling.state import ModelStateAdapter, require_reference


class ModelOutputContract:
    schema_id = "pypsa-network-modeling-output/1.0"

    def build(
        self, *, binding_id: str, context: object,
        committed_answers: tuple[object, ...],
    ) -> Mapping[str, object]:
        del committed_answers
        dumped = context.model_dump(mode="json")
        if dumped.get("binding_id") != binding_id:
            raise ValueError("PyPSA model output binding differs")
        state = dumped.get("state")
        view = ModelStateAdapter().build_context(binding_id=binding_id, state=state)
        return {
            "active_model_ref": view.state["active_model_ref"],
            "result_refs": sorted(view.state["results"]),
        }

    def validate(self, payload: Mapping[str, object]) -> None:
        if set(payload) != {"active_model_ref", "result_refs"}:
            raise ValueError("PyPSA model output fields are invalid")
        active = payload["active_model_ref"]
        if active is not None:
            require_reference(active, "model")
        refs = payload["result_refs"]
        if not isinstance(refs, (list, tuple)) or any(
            require_reference(ref, "result") != ref for ref in refs
        ):
            raise ValueError("PyPSA model output references are invalid")


class ModelPresentationProvider:
    def render_context(self, context: object) -> Mapping[str, object]:
        raw = context.model_dump(mode="json") if hasattr(context, "model_dump") else context
        if not isinstance(raw, Mapping):
            raise ValueError("PyPSA model context is invalid")
        if "domains" in raw:
            matches = [
                (key, value) for key, value in raw["domains"].items()
                if isinstance(value, Mapping) and value.get("schema_id") == ModelStateAdapter.schema_id
            ]
            if len(matches) != 1:
                raise ValueError("PyPSA model state envelope is ambiguous")
            binding_id, envelope = matches[0]
            state = envelope.get("state")
        else:
            binding_id, state = raw.get("binding_id"), raw.get("state")
        if not isinstance(binding_id, str) or not isinstance(state, Mapping):
            raise ValueError("PyPSA model state is unavailable")
        view = ModelStateAdapter().build_context(binding_id=binding_id, state=state)
        return {
            "binding_id": binding_id,
            "active_model_ref": view.state["active_model_ref"],
            "result_count": len(view.state["results"]),
        }

    def render_report(self, context: object) -> str:
        view = self.render_context(context)
        return (
            "## PyPSA Network Modeling\n\n"
            f"Active model: {view['active_model_ref'] or 'none'}\n"
            f"Admitted results: {view['result_count']}\n"
        )
