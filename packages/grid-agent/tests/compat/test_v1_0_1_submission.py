from __future__ import annotations

import json
from pathlib import Path

from capability_agent.application.workspace import ApplicationWorkspace

from grid_agent.compat.v1_0_1_submission import write_submission_checkpoint


def test_submission_checkpoint_writes_only_v1_envelopes_in_turn_order(tmp_path: Path) -> None:
    workspace = ApplicationWorkspace.create(tmp_path / "runs", "submission-run", ("grid",))
    path = write_submission_checkpoint(
        workspace=workspace, questions=("first", "second"), answers=("answer one", "answer two")
    )
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert lines == [
        {"question_id": "submission-run-t001", "answer_output": "answer one"},
        {"question_id": "submission-run-t002", "answer_output": "answer two"},
    ]
    assert all(set(line) == {"question_id", "answer_output"} for line in lines)


def test_submission_checkpoint_replaces_prior_complete_contents(tmp_path: Path) -> None:
    workspace = ApplicationWorkspace.create(tmp_path / "runs", "submission-run", ("grid",))
    path = write_submission_checkpoint(workspace=workspace, questions=("first", "second"), answers=("one",))
    write_submission_checkpoint(workspace=workspace, questions=("first", "second"), answers=("one", "two"))
    assert [json.loads(line) for line in path.read_text().splitlines()] == [
        {"question_id": "submission-run-t001", "answer_output": "one"},
        {"question_id": "submission-run-t002", "answer_output": "two"},
    ]
