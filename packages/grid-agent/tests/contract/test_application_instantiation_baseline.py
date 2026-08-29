import json
from pathlib import Path
from typing import Sequence

import pytest
from typer.testing import CliRunner

from grid_agent.cli.app import app
from grid_agent.reporting import load_questions


class _ApplicationCliRunner:
    def __init__(self) -> None:
        self._runner = CliRunner()

    def invoke(self, arguments: Sequence[str]):
        return self._runner.invoke(app, list(arguments))


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


@pytest.fixture
def cli_runner() -> _ApplicationCliRunner:
    return _ApplicationCliRunner()


def test_canonical_business_task_files_are_distinct_and_nonempty(
    repo_root: Path,
) -> None:
    task = load_questions(repo_root / "validation/questions/task.md.txt")
    test = load_questions(repo_root / "validation/questions/test.md.txt")
    assert task
    assert test
    assert task != test


def test_grid_compatibility_envelope_has_exact_keys(
    cli_runner: _ApplicationCliRunner,
) -> None:
    result = cli_runner.invoke(["run", "--offline", "母线电压正常运行范围是多少?"])
    assert result.exit_code == 0
    assert set(json.loads(result.stdout)) == {"question_id", "answer_output"}
