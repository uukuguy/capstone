"""Atomic writer for the historical v1.0.1 application submission envelope."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path

from capability_agent.application.workspace import ApplicationWorkspace


def write_submission_checkpoint(
    *,
    workspace: ApplicationWorkspace,
    questions: Iterable[str],
    answers: Iterable[str],
) -> Path:
    """Replace the run's answer submission with accepted answers atomically."""
    question_values = tuple(questions)
    answer_values = tuple(answers)
    if len(answer_values) > len(question_values):
        raise ValueError("accepted answers exceed application questions")
    payload = "".join(
        json.dumps(
            {"question_id": f"{workspace.run_id}-t{ordinal:03d}", "answer_output": answer},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
        for ordinal, answer in enumerate(answer_values, start=1)
    )
    target = workspace.output_path / "answers.jsonl"
    temporary = target.with_name(f".{target.name}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(target)
    return target
