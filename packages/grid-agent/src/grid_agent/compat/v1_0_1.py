"""Lossy output and naming compatibility for grid-agent 1.0.1.

The adapter owns only the historical delivery projection.  It never receives
an executor or authority and therefore cannot alter simulator truth, evidence
admission, answer auditing, or the validated Kernel result.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from capability_agent.application.output import ApplicationResult


if TYPE_CHECKING:
    from capability_agent.application.runner import ApplicationOutcome


LEGACY_COMMANDS = ("run", "analysis", "report")
LEGACY_CORE_TOOL_ALIASES = (
    "grid_record_decision",
    "grid_context_get",
)


class V1_0_1CompatibilityAdapter:
    """Render the exact two-field envelope required by the old entry point."""

    def render(self, *, question_id: str, answer_output: str) -> str:
        if not isinstance(question_id, str) or not question_id:
            raise ValueError("question_id must be non-empty text")
        if not isinstance(answer_output, str):
            raise ValueError("answer_output must be text")
        return json.dumps(
            {"question_id": question_id, "answer_output": answer_output},
            ensure_ascii=False,
        ) + "\n"

    def project_result(
        self,
        result: ApplicationResult,
        *,
        question_id: str | None = None,
        answer_output: str | None = None,
    ) -> dict[str, str]:
        """Return a copy of the legacy shape without changing ``result``.

        ``answer_output`` is intentionally supplied by the legacy report
        caller; the adapter does not reinterpret or reconstruct domain data.
        """

        if not isinstance(result, ApplicationResult):
            raise TypeError("result must be a validated ApplicationResult")
        resolved_question_id = question_id or result.core.run_id
        resolved_answer_output = answer_output
        if resolved_answer_output is None:
            resolved_answer_output = _legacy_report_path(result)
        if not isinstance(resolved_answer_output, str):
            raise ValueError("answer_output must be text")
        return {
            "question_id": resolved_question_id,
            "answer_output": resolved_answer_output,
        }

    def render_outcome(
        self,
        outcome: ApplicationOutcome,
        *,
        question_id: str | None = None,
        project_root: Path | None = None,
    ) -> str:
        """Project a generic outcome to the historical report-path envelope."""

        if not hasattr(outcome, "result"):
            raise TypeError("outcome must be an application outcome")
        report_path = getattr(outcome, "report_path", None)
        answer_output = _relative_report_path(report_path, project_root)
        return self.render(
            question_id=question_id or str(getattr(outcome, "run_id", None) or outcome.result.core.run_id),
            answer_output=answer_output,
        )


def build_grid_v1_0_1_compatibility_adapter() -> V1_0_1CompatibilityAdapter:
    return V1_0_1CompatibilityAdapter()


def _legacy_report_path(result: ApplicationResult) -> str:
    return f"runs/{result.core.run_id}/report.md"


def _relative_report_path(path: object, project_root: Path | None) -> str:
    if isinstance(path, Path):
        try:
            root = (project_root or Path.cwd()).resolve()
            return path.resolve().relative_to(root).as_posix()
        except (OSError, ValueError):
            return str(path)
    return ""


__all__ = [
    "LEGACY_COMMANDS",
    "LEGACY_CORE_TOOL_ALIASES",
    "V1_0_1CompatibilityAdapter",
    "build_grid_v1_0_1_compatibility_adapter",
]
