from pathlib import Path

import pytest

from validation.question_files import load_questions


def test_question_lines_ignore_comments_and_blanks(tmp_path):
    source = tmp_path / "questions.txt"
    source.write_text("# title\n\n线路11连接哪两个母线?\n  母线电压范围?  \n")
    assert load_questions(source) == ("线路11连接哪两个母线?", "母线电压范围?")


def test_empty_question_file_fails(tmp_path):
    source = tmp_path / "questions.txt"
    source.write_text("# title\n\n")
    with pytest.raises(ValueError, match="contains no questions"):
        load_questions(source)
