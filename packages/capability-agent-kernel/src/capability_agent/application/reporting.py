"""Generic report structure with domain presentation kept behind a port."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from capability_agent.application.errors import PresentationError


@dataclass(frozen=True, slots=True)
class ReportPublication:
    status: Literal["published", "unavailable"]
    report_ref: str | None
    diagnostic_codes: tuple[str, ...] = ()


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
        assurance_values = tuple(_text_values(assurances, "assurances"))
        trajectory_values = tuple(_text_values(trajectories, "trajectories"))
        reference_values = tuple(_text_values(references, "references"))
        lines = ["# Application report", ""]
        for index, question in enumerate(question_values, start=1):
            lines.extend((f"## Question {index}", "", question, ""))
            if index <= len(answer_values):
                lines.extend(("### Answer", "", answer_values[index - 1], ""))
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


__all__ = ["GenericReportShell", "ReportPublication"]
