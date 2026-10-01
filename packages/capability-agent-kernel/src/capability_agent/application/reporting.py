"""Generic report structure with domain presentation kept behind a port."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from capability_agent.application.errors import PresentationError


@dataclass(frozen=True, slots=True)
class ReportPublication:
    status: Literal["published", "unavailable"]
    report_ref: str | None
    diagnostic_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ToolFailure:
    """A bounded, reader-facing summary of one failed capability call."""

    capability_id: str
    message: str
    code: str | None = None
    turn_id: str | None = None
    observation_ref: str | None = None


def extract_tool_failures(
    diagnostics: Iterable[Mapping[str, object]],
) -> tuple[ToolFailure, ...]:
    """Normalize failed tool diagnostics without depending on a domain pack."""

    failures: list[ToolFailure] = []
    seen: set[tuple[str, str | None, str | None, str | None]] = set()
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, Mapping):
            continue
        if diagnostic.get("event_type") != "tool.failed" and diagnostic.get("ok") is not False:
            continue
        error = diagnostic.get("error")
        error_mapping = error if isinstance(error, Mapping) else {}
        capability = _diagnostic_text(
            diagnostic, "capability_id", "capability", "tool_name"
        ) or "已发布能力"
        code = _diagnostic_text(diagnostic, "error_code", "code") or _diagnostic_text(
            error_mapping, "error_code", "code"
        )
        message = _diagnostic_text(
            diagnostic, "error_message", "message", "detail"
        ) or _diagnostic_text(error_mapping, "error_message", "message", "detail")
        if not message or message == "capability returned a bounded failure":
            message = "工具返回受限失败"
        turn_id = _diagnostic_text(diagnostic, "turn_id")
        observation_ref = _diagnostic_text(diagnostic, "observation_ref")
        failure = ToolFailure(
            capability_id=_bounded_text(capability),
            message=_bounded_text(message),
            code=_bounded_text(code) if code else None,
            turn_id=_bounded_text(turn_id) if turn_id else None,
            observation_ref=_bounded_text(observation_ref) if observation_ref else None,
        )
        identity = (failure.capability_id, failure.code, failure.message, failure.turn_id)
        if identity not in seen:
            seen.add(identity)
            failures.append(failure)
    return tuple(failures)


def format_tool_failure(failure: ToolFailure) -> str:
    """Format a concise failure line shared by all application reports."""

    suffix = f"（错误码 {failure.code}）" if failure.code else ""
    return (
        f"调用已发布能力 `{failure.capability_id}` 失败；"
        f"失败原因：{failure.message}{suffix}"
    )


def _diagnostic_text(value: Mapping[str, object], *keys: str) -> str | None:
    for key in keys:
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _bounded_text(value: str, *, limit: int = 240) -> str:
    compact = re.sub(r"\s+", " ", value).strip()
    return compact if len(compact) <= limit else compact[: limit - 1].rstrip() + "…"


class GenericReportShell:
    """Render common question/answer/trace/reference records.

    The shell deliberately treats domain context as opaque.  A selected
    presentation provider may append labels and business summaries, but the
    shell never derives those values itself.
    """

    def render(
        self,
        *,
        questions: Iterable[str] = (),
        answers: Iterable[str] = (),
        answer_summaries: Iterable[str] = (),
        assurances: Iterable[str] = (),
        trajectories: Iterable[str] = (),
        references: Iterable[str] = (),
        context: object | None = None,
        presentation: object | None = None,
        core: Mapping[str, object] | None = None,
        domains: Mapping[str, object] | None = None,
    ) -> str:
        question_values = tuple(_text_values(questions, "questions"))
        answer_values = tuple(_text_values(answers, "answers"))
        summary_values = tuple(_text_values(answer_summaries, "answer_summaries"))
        assurance_values = tuple(_text_values(assurances, "assurances"))
        trajectory_values = tuple(_text_values(trajectories, "trajectories"))
        reference_values = tuple(_text_values(references, "references"))
        lines = ["# Application report", ""]
        for index, question in enumerate(question_values, start=1):
            lines.extend((f"## Question {index}", "", question, ""))
            if index <= len(answer_values):
                summary = summary_values[index - 1] if index <= len(summary_values) else ""
                lines.extend(("### 回答摘要", "", summary or "未记录独立回答摘要。", ""))
                lines.extend(("### 正式回答", "", answer_values[index - 1], ""))
                assurance = assurance_values[index - 1] if index <= len(assurance_values) else "unknown"
                lines.extend((f"Guarantee scope: {assurance}", ""))
        if trajectory_values:
            lines.extend(("## Trajectory", "", *_bullets(trajectory_values), ""))
        if reference_values:
            lines.extend(("## References", "", *_bullets(reference_values), ""))
        if core is not None:
            lines.extend(("## Framework record", "", _json_text(core), ""))
        if domains is not None:
            lines.extend(("## Domain records", "", _json_text(domains), ""))
        if presentation is not None:
            renderer = getattr(presentation, "render_report", None)
            if not callable(renderer):
                raise PresentationError("domain presentation provider cannot render a report")
            try:
                rendered = renderer(context)
            except Exception:
                raise PresentationError("domain report presentation failed") from None
            if not isinstance(rendered, str):
                raise PresentationError("domain report presentation must return text")
            lines.extend(("## Domain summary", "", rendered, ""))
        return "\n".join(lines).rstrip() + "\n"


def _text_values(values: Iterable[str], field_name: str) -> list[str]:
    try:
        result = list(values)
    except TypeError:
        raise PresentationError(f"report {field_name} are invalid") from None
    if any(not isinstance(value, str) for value in result):
        raise PresentationError(f"report {field_name} must contain text")
    return result


def _bullets(values: Iterable[str]) -> list[str]:
    return [f"- {value}" for value in values]


def _json_text(value: Mapping[str, object]) -> str:
    try:
        return "```json\n" + json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n```"
    except (TypeError, ValueError):
        raise PresentationError("framework report record is not serializable") from None


__all__ = [
    "GenericReportShell",
    "ReportPublication",
    "ToolFailure",
    "extract_tool_failures",
    "format_tool_failure",
]
