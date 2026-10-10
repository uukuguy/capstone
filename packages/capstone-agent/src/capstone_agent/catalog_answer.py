"""Application-owned completeness projection for registered model metadata."""

from __future__ import annotations

from collections.abc import Mapping
import re

from .turn_router import is_model_catalog_listing


_SUBSET_REQUEST = re.compile(
    r"示例|举例|几个|部分|推荐|[零一二三四五六七八九十百两\d]+\s*(?:个|种|款|项)"
    r"|\b(?:examples?|some|few|first|top|recommend|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b",
    re.IGNORECASE,
)


def _contains_identifier(text: str, identifier: str) -> bool:
    return re.search(r"(?<![A-Za-z0-9_/-])" + re.escape(identifier) + r"(?![A-Za-z0-9_/-])", text) is not None


def _cell(value: str) -> str:
    return " ".join(value.split()).replace("\\", "\\\\").replace("|", "\\|").replace("`", "\\`")


def complete_catalog_answer(
    instruction: str, answer: str, catalog: Mapping[str, object] | None,
) -> str | None:
    """Replace a missing-entry list using only this Attempt's bounded catalog.

    Complete answers retain the model's wording. General explanations and mixed
    calculation requests are outside this presentation projection.
    """
    if not is_model_catalog_listing(instruction) or catalog is None or _SUBSET_REQUEST.search(instruction):
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
    families = {str(item["implementation_family"]) for item in entries}
    requested = {family for family in families if _contains_identifier(instruction.lower(), family.lower())}
    selected = [item for item in entries if not requested or item["implementation_family"] in requested]
    if all(_contains_identifier(answer, str(item["model_id"])) for item in selected):
        return None
    scope = " / ".join(sorted(requested)) if requested else "应用"
    lines = [f"已注册模型共 {len(selected)} 个（{_cell(scope)}）：", "",
             "| 模型名称 | 模型标识 | 实现系列 | 状态 |", "| --- | --- | --- | --- |"]
    for item in selected:
        status = "暂不可用" if item.get("available") is False else "可用" if item.get("available") is True else "已注册"
        lines.append(f"| {_cell(str(item['display_name']))} | `{_cell(str(item['model_id']))}` | {_cell(str(item['implementation_family']))} | {status} |")
    lines.extend(["", "如需分析其中的模型，请通过模型选择控件切换到该模型。"])
    projected = "\n".join(lines)
    return projected if len(projected) <= 64_000 else None
