"""Pandapower-owned context, labels, and business presentation helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, cast

from pandapower_domain.models import AnalysisContext


CONTEXT_VIEW_VERSION = "pandapower-context-view/1.0"

SEMANTIC_TOOL_TITLES = {
    "environment.describe": "核对仿真器协议和已发布能力",
    "model.list": "确认可用的已注册网络模型",
    "context.open": "打开只读网络仿真环境上下文",
    "context.get": "读取已打开的仿真环境上下文",
    "model.element.get": "定位问题涉及的网络元件",
    "model.dataset.describe": "核对可查询的数据集与字段",
    "model.dataset.query": "查询网络模型数据",
    "topology.branch.endpoints.get": "核查支路两端母线",
    "topology.components.get": "核查网络拓扑连通性",
    "analysis.powerflow.ac.run": "运行交流潮流计算",
    "result.branches.rank": "按支路运行指标筛选和排序",
    "analysis.contingency.n_minus_one.run": "执行单支路 N-1 静态安全校核",
    "evidence.get": "读取已持久化的仿真证据",
    "grid_guide_open": "读取已发布的领域操作指南",
    "grid_submit_answer": "提交带结构化证据的最终答案",
}


class PandapowerProjectionIntegrityError(RuntimeError):
    """A business result node lacks verified simulator artifacts."""


class ArtifactResolver(Protocol):
    def verify(self, reference: str) -> Any: ...


class PandapowerPresentationProvider:
    """Render bounded model context and domain report summaries."""

    def render_context(self, context: object) -> Mapping[str, object]:
        return render_pandapower_context(context)

    def render_report(self, context: object) -> str:
        return render_pandapower_report(self.render_context(context))

    def render_summary(self, context: object) -> Mapping[str, object]:
        return self.render_context(context)


def semantic_tool_title(capability: str) -> str:
    """Return the localized title registered for a pandapower capability."""

    return SEMANTIC_TOOL_TITLES.get(capability, capability)


def is_verified_result_capability(capability: str) -> bool:
    return capability.startswith(("analysis.", "result."))


def require_verified_simulator_artifacts(
    references: Sequence[str], artifacts: ArtifactResolver
) -> None:
    documents = tuple(artifacts.verify(reference) for reference in references)
    if not documents or any(
        getattr(document, "authority", None) != "gridctl"
        or getattr(document, "integrity", None) != "verified"
        for document in documents
    ):
        raise PandapowerProjectionIntegrityError(
            "numerical business node requires a verified simulator artifact"
        )


def render_pandapower_context(context: object) -> dict[str, object]:
    """Return only bounded JSON summaries from a domain context object."""

    if isinstance(context, AnalysisContext):
        return _legacy_context_summary(context)
    raw = _model_mapping(context)
    state_value = raw.get("state")
    if isinstance(state_value, Mapping):
        state = state_value
        result: dict[str, object] = {
            "schema_version": CONTEXT_VIEW_VERSION,
            "binding_id": raw.get("binding_id"),
            "model": state.get("model"),
            "operating_state": state.get("operating_state"),
            "constraints": _records(state.get("constraints")),
            "scenarios": _records(state.get("scenarios")),
            "calculations": _records(state.get("calculations")),
            "capabilities": _records(state.get("capabilities")),
        }
    else:
        result = {"schema_version": CONTEXT_VIEW_VERSION, **raw}
    return cast(dict[str, object], _sanitize(result))


def render_pandapower_report(context: Mapping[str, object]) -> str:
    model = context.get("model")
    lines = ["## Pandapower Static Analysis", ""]
    if isinstance(model, Mapping):
        lines.append(f"- Model: {model.get('model_id', 'unknown')}")
        counts = model.get("counts")
        if isinstance(counts, Mapping) and counts:
            lines.append(
                "- Network: "
                + ", ".join(
                    f"{key}={value}"
                    for key, value in sorted(counts.items(), key=lambda item: str(item[0]))
                )
            )
    for field, title, identity in (
        ("scenarios", "Scenarios", "scenario_ref"),
        ("calculations", "Calculations", "result_ref"),
    ):
        records = context.get(field)
        if isinstance(records, list) and records:
            lines.extend(["", f"### {title}", ""])
            lines.extend(
                f"- {record.get(identity, field[:-1])}: {record.get('status', 'unknown')}"
                for record in records
                if isinstance(record, Mapping)
            )
    return "\n".join(lines) + "\n"


def _legacy_context_summary(context: AnalysisContext) -> dict[str, object]:
    model = context.domain_state.model
    return cast(
        dict[str, object],
        _sanitize(
            {
                "schema_version": CONTEXT_VIEW_VERSION,
                "analysis_id": context.analysis_id,
                "revision": context.revision,
                "state_hash": context.state_hash,
                "status": context.status,
                "active_model": (
                    {
                        "context_ref": model.context_ref,
                        "revision_ref": model.revision_ref,
                        "model_id": model.model_id,
                        "source": model.source,
                        "counts": model.counts,
                    }
                    if model is not None
                    else None
                ),
                "constraints": [
                    item.model_dump(mode="json")
                    for item in context.domain_state.constraints.values()
                ],
                "scenarios": [
                    item.model_dump(mode="json")
                    for item in context.domain_state.scenarios.values()
                ],
                "calculations": [
                    item.model_dump(mode="json")
                    for item in context.domain_state.calculations.values()
                ],
            }
        ),
    )


def _model_mapping(value: object) -> dict[str, object]:
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            dumped = dump(mode="python")
        except TypeError:
            dumped = dump()
        if isinstance(dumped, Mapping):
            return {str(key): item for key, item in dumped.items()}
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def _records(value: object) -> list[object]:
    if isinstance(value, Mapping):
        return [item for _, item in sorted(value.items(), key=lambda item: str(item[0]))]
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _sanitize(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize(item)
            for key, item in value.items()
            if str(key).casefold() not in {"raw", "dataframe", "pandapower_net"}
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    if value is None or type(value) in {str, int, float, bool}:
        return value
    return None


__all__ = [
    "ArtifactResolver",
    "CONTEXT_VIEW_VERSION",
    "PandapowerPresentationProvider",
    "PandapowerProjectionIntegrityError",
    "SEMANTIC_TOOL_TITLES",
    "is_verified_result_capability",
    "render_pandapower_context",
    "render_pandapower_report",
    "require_verified_simulator_artifacts",
    "semantic_tool_title",
]
