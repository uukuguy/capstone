"""Shared formatting rules for reader-facing application reports."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass


_MAX_SUMMARY_CODEPOINTS = 220
ANSWER_BUNDLE_INSTRUCTION = (
    "完成所有必要的工具调用后，只返回一个 JSON 对象，不要使用 Markdown 代码围栏。"
    "对象必须包含 answer 和 summary 两个字符串字段。answer 是完整正式回答；"
    "summary 是 answer 的简体中文 1–2 句摘要，只能压缩 answer 中已有的事实、数值、"
    "结论和限制，不得新增任何信息。"
)


@dataclass(frozen=True, slots=True)
class AnswerBundle:
    """The model's formal answer and its optional process summary."""

    answer: str
    summary: str | None
    diagnostic_codes: tuple[str, ...] = ()


def parse_answer_bundle(value: str) -> AnswerBundle:
    """Parse the opt-in JSON response while preserving legacy plain text."""

    if not isinstance(value, str) or not value.strip():
        return AnswerBundle("", None, ("answer_bundle_invalid",))
    raw = value.strip()
    candidate = raw
    fenced = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", raw, re.IGNORECASE)
    if fenced is not None:
        candidate = fenced.group(1).strip()
    decoded = _decode_json_object(candidate)
    if decoded is None:
        return AnswerBundle(raw, None, ("answer_bundle_unavailable",))
    raw_answer = decoded.get("answer")
    if not isinstance(raw_answer, str):
        return AnswerBundle(raw, None, ("answer_bundle_invalid",))
    answer = raw_answer.strip()
    if not answer:
        return AnswerBundle(raw, None, ("answer_bundle_invalid",))
    summary = decoded.get("summary")
    if not isinstance(summary, str) or not summary.strip() or len(summary.strip()) > _MAX_SUMMARY_CODEPOINTS:
        return AnswerBundle(answer, None, ("answer_summary_invalid",))
    return AnswerBundle(answer, summary.strip(), ())


def _decode_json_object(value: str) -> dict[str, object] | None:
    """Decode a JSON answer bundle, tolerating a provider preamble."""

    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        decoded = None
        for index, character in enumerate(value):
            if character != "{":
                continue
            try:
                candidate, _ = decoder.raw_decode(value[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                decoded = candidate
                break
    return decoded if isinstance(decoded, dict) else None


_PLANNING_PREFIX = re.compile(
    r"\b(?:i['’]?ll|i will|now|starting|probe|a model)\b", re.IGNORECASE
)


def format_report_answer(value: str) -> str:
    """Keep the formal answer and subordinate its Markdown to ``### 回答``.

    Providers may stream a short English planning preamble before a Markdown
    answer.  The raw answer artifact remains unchanged; this is only the
    reader-facing report projection shared by all application report shells.
    """

    text = value.strip()
    candidates = [match.start() for match in (
        re.search(r"\*\*[^*]+\*\*", text),
        re.search(r"(?<!\w)#{1,3}\s+", text),
    ) if match is not None]
    if candidates:
        start = min(candidates)
        if _PLANNING_PREFIX.search(text[:start]):
            text = text[start:].strip()
    return _demote_headings(text)


def _demote_headings(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        indent, hashes, spacing = match.groups()
        level = min(6, max(4, len(hashes) + 3))
        return f"{indent}{'#' * level}{spacing}"

    return re.sub(r"^(\s*)(#{1,6})(\s+)", replace, value, flags=re.MULTILINE).strip()


__all__ = [
    "ANSWER_BUNDLE_INSTRUCTION",
    "AnswerBundle",
    "format_report_answer",
    "parse_answer_bundle",
]
