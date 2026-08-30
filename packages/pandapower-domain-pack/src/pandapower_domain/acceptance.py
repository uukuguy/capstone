"""Acceptance declarations for the first complete pandapower application."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PandapowerAcceptanceCase:
    case_id: str
    instructions_path: Path | None = None
    mode: str = "offline"
    description: str = ""


class PandapowerAcceptanceProfile:
    """Declare acceptance inputs without executing provider or simulator I/O."""

    def offline_cases(self) -> tuple[PandapowerAcceptanceCase, ...]:
        return (
            PandapowerAcceptanceCase(
                case_id="profile-completeness",
                mode="offline",
                description="all pandapower providers are declared",
            ),
        )

    def scripted_cases(self) -> tuple[PandapowerAcceptanceCase, ...]:
        return (
            PandapowerAcceptanceCase(
                case_id="pandapower-scripted-task",
                instructions_path=Path(
                    "validation/application/pandapower-scripted-task.json"
                ),
                mode="scripted",
                description="deterministic context reuse and answer lineage",
            ),
            PandapowerAcceptanceCase(
                case_id="pandapower-scripted-test",
                instructions_path=Path(
                    "validation/application/pandapower-scripted-test.json"
                ),
                mode="scripted",
                description="deterministic output and audit validation",
            ),
            PandapowerAcceptanceCase(
                case_id="task10-context-reuse",
                mode="scripted",
                description="Task 10 context reuse case",
            ),
            PandapowerAcceptanceCase(
                case_id="task10-answer-audit",
                mode="scripted",
                description="Task 10 answer audit case",
            ),
            PandapowerAcceptanceCase(
                case_id="task10-output-contract",
                mode="scripted",
                description="Task 10 output contract case",
            ),
        )

    def provider_cases(self) -> tuple[PandapowerAcceptanceCase, ...]:
        return (
            PandapowerAcceptanceCase(
                case_id="pandapower-task",
                instructions_path=Path("validation/questions/task.md.txt"),
                mode="provider",
                description="repository pandapower task questions",
            ),
            PandapowerAcceptanceCase(
                case_id="pandapower-test",
                instructions_path=Path("validation/questions/test.md.txt"),
                mode="provider",
                description="repository pandapower test questions",
            ),
        )


__all__ = ["PandapowerAcceptanceCase", "PandapowerAcceptanceProfile"]
