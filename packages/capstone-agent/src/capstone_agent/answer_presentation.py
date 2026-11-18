"""Project explicit public text without classifying natural language."""
import json
import re

OPEN = '<capstone-answer>'
CLOSE = '</capstone-answer>'
_TOOL_TRAILER = re.compile(r'</｜｜DSML｜｜ parameter>\s*</｜｜DSML｜｜ invoke>\s*</｜｜DSML｜｜ calls>\s*\Z')
_SUMMARY_OPEN = '<capstone-answer-summary>'


def _answer_object(text: str) -> dict[str, str] | None:
    try:
        value = json.loads(text)
    except ValueError:
        return None
    if (isinstance(value, dict) and set(value) == {'answer', 'summary'}
            and all(isinstance(item, str) and item.strip() for item in value.values())):
        return value
    return None


def public_answer(text: str, *, answer_format: str | None = None) -> str:
    if answer_format == 'formal-and-core/1' and OPEN in text:
        text = _TOOL_TRAILER.sub('', text)
    if OPEN not in text and CLOSE not in text:
        return text  # Older protocols: do not guess or delete prose.
    if text.count(OPEN) != 1 or text.count(CLOSE) != 1:
        if answer_format == 'formal-and-core/1' and OPEN in text:
            before, _, body = text.rpartition(OPEN)
            candidate = body.strip()
            if CLOSE not in before:
                while candidate.endswith(CLOSE):
                    candidate = candidate[:-len(CLOSE)].rstrip()
                if _answer_object(candidate) is not None:
                    return candidate
        raise ValueError('answer_presentation_invalid')
    _, remainder = text.split(OPEN, 1)
    body, after = remainder.split(CLOSE, 1)
    body, after = body.strip(), after.strip()
    if body and answer_format == 'formal-and-core/1' and after.startswith(_SUMMARY_OPEN):
        supplemental = _answer_object(after.removeprefix(_SUMMARY_OPEN).strip())
        if supplemental is not None and _answer_object(body) is None:
            return json.dumps({'answer': body, 'summary': supplemental['summary']}, ensure_ascii=False)
    if not body or after:
        raise ValueError('answer_presentation_invalid')
    return body
