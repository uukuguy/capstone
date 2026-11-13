"""Read the repository's ordered validation questions."""

from pathlib import Path


def load_questions(path: Path) -> tuple[str, ...]:
    lines = path.read_text(encoding="utf-8").splitlines()
    questions = tuple(line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#"))
    if not questions:
        raise ValueError(f"question file contains no questions: {path}")
    return questions
