"""Deterministic corrections to the presentation of an admitted answer."""

import re
from dataclasses import dataclass
from functools import lru_cache

from .harness_validation import Decision, RuleBundle, load_rule_bundle, published_rule_bundle_bytes

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_PIPE = re.compile(r"(?<!\\)\|")
_BROKEN_BREAK = re.compile(r"(?<!\\)\|n\|")
_COLUMN_SEPARATOR = re.compile(r":?-+:?")


@dataclass(frozen=True, slots=True)
class AnswerCorrection:
    answer: str
    table_row_breaks: int = 0


def _table_cells(line: str) -> list[str]:
    if not re.fullmatch(r" {0,3}\|.*\|[ \t\r]*", line):
        return []
    return [cell.strip() for cell in _PIPE.split(line.strip()[1:-1])]


def correct_answer_presentation(answer: str) -> AnswerCorrection:
    """Restore known row breaks only where every row matches the table header."""
    if "|n|" not in answer:
        return AnswerCorrection(answer)

    output = []
    fence = previous = ""
    columns = corrections = 0
    for line in answer.split("\n"):
        marker = _FENCE.match(line)
        if marker and (not fence or (
            marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip()
        )):
            fence = "" if fence else marker[1]
            previous = ""
            columns = 0
        elif not fence:
            cells = _table_cells(line)
            if cells and len(cells) == len(_table_cells(previous)) and all(
                _COLUMN_SEPARATOR.fullmatch(cell) for cell in cells
            ):
                columns = len(cells)
            elif columns and len(cells) > columns and "|n|" in line:
                candidate, count = _BROKEN_BREAK.subn("|\n|", line)
                if count and all(len(_table_cells(row)) == columns for row in candidate.split("\n")):
                    corrections += count
                    line = candidate
            elif not cells:
                columns = 0
            previous = line
        output.append(line)
    return AnswerCorrection("\n".join(output), corrections)


def _table_row_break_rule(answer: str) -> Decision[str]:
    correction = correct_answer_presentation(answer)
    if not correction.table_row_breaks:
        return Decision.accepted(answer)
    return Decision.corrected(
        correction.answer, "table_row_breaks_restored", count=correction.table_row_breaks
    )


@lru_cache(maxsize=1)
def presentation_rule_bundle() -> RuleBundle[str]:
    return load_rule_bundle(published_rule_bundle_bytes(), {"markdown_table_row_breaks": _table_row_break_rule})
