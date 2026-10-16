"""Application-owned completeness projection for registered model metadata."""

from __future__ import annotations

from collections.abc import Mapping
import re

def _contains_identifier(text: str, identifier: str) -> bool:
    return re.search(r"(?<![A-Za-z0-9_/-])" + re.escape(identifier) + r"(?![A-Za-z0-9_/-])", text) is not None


def _cell(value: str) -> str:
    return " ".join(value.split()).replace("\\", "\\\\").replace("|", "\\|").replace("`", "\\`")


def complete_catalog_answer(
    instruction: str, answer: str, catalog: Mapping[str, object] | None,
    *, full_catalog_requested: bool = False,
) -> str | None:
    """Complete an explicitly selected full catalog from bounded metadata.

    ``instruction`` is retained for call compatibility and is not interpreted.
    The caller must select the full catalog scope. This helper does not infer
    families, shortlists, mixed requests, or intent from reader-facing prose.
    Complete answers retain the model's wording.
    """
    if full_catalog_requested is not True or catalog is None:
        return None
    models = catalog.get("models")
    if not isinstance(models, list) or not models or len(models) > 128:
        return None
    entries: list[Mapping[str, object]] = []
    for item in models:
        if not isinstance(item, Mapping):
            return None
        if any(not isinstance(item.get(key), str) or not str(item[key]).strip() or len(str(item[key])) > 256
               for key in ("model_id", "display_name", "implementation_family")):
            return None
        entries.append(item)
    if all(_contains_identifier(answer, str(item["model_id"])) for item in entries):
        return None
    lines = [f"已注册模型共 {len(entries)} 个（应用）：", "",
             "| 模型名称 | 模型标识 | 实现系列 | 状态 |", "| --- | --- | --- | --- |"]
    for item in entries:
        status = "暂不可用" if item.get("available") is False else "可用" if item.get("available") is True else "已注册"
        lines.append(f"| {_cell(str(item['display_name']))} | `{_cell(str(item['model_id']))}` | {_cell(str(item['implementation_family']))} | {status} |")
    lines.extend(["", "如需分析其中的模型，请通过模型选择控件切换到该模型。"])
    projected = "\n".join(lines)
    return projected if len(projected) <= 64_000 else None
