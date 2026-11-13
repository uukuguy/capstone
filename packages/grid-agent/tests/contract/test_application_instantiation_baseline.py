from pathlib import Path

from validation.question_files import load_questions


def test_canonical_business_task_files_are_distinct_and_nonempty(
) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    task = load_questions(repo_root / "validation/questions/task.md.txt")
    test = load_questions(repo_root / "validation/questions/test.md.txt")
    assert task
    assert test
    assert task != test
