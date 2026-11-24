"""Project explicit public text without classifying natural language."""
import json
import re

OPEN = '<capstone-answer>'
CLOSE = '</capstone-answer>'
_TOOL_TRAILER = re.compile(r'</｜｜DSML｜｜ parameter>\s*</｜｜DSML｜｜ invoke>\s*</｜｜DSML｜｜ calls>\s*\Z')
_SUMMARY_OPEN = '<capstone-answer-summary>'
_EXPLICIT_BODY = re.compile(re.escape(OPEN) + r'((?:(?!' + re.escape(OPEN) + r').)*?)' + re.escape(CLOSE), re.DOTALL)
_FORMAT_NOTICE = '> 回答格式异常。已保留可确认的正式回答。'


class AnswerPresentationError(ValueError):
    """The public answer cannot be isolated from its presentation envelope."""


def _json_object(text: str, *, strict: bool = True) -> dict | None:
    try:
        value = json.loads(text, strict=strict)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _answer_object(text: str, *, strict: bool = True) -> dict[str, str] | None:
    value = _json_object(text, strict=strict)
    if (value is not None and set(value) == {'answer', 'summary'}
            and all(isinstance(item, str) and item.strip() for item in value.values())):
        return value
    return None


def public_answer(text: str, *, answer_format: str | None = None, recover_unique: bool = False) -> str:
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
        if recover_unique:
            bodies = {body.strip() for body in _EXPLICIT_BODY.findall(text) if body.strip()}
            if len(bodies) == 1:
                candidate = bodies.pop()
                if answer_format != 'formal-and-core/1':
                    return candidate + '\n\n' + _FORMAT_NOTICE
                bundle = _answer_object(candidate, strict=False)
                if bundle is not None:
                    bundle['answer'] += '\n\n' + _FORMAT_NOTICE
                    return json.dumps(bundle, ensure_ascii=False)
        raise AnswerPresentationError('answer_presentation_invalid')
    _, remainder = text.split(OPEN, 1)
    body, after = remainder.split(CLOSE, 1)
    body, after = body.strip(), after.strip()
    if body and after and answer_format == 'formal-and-core/1':
        bundle = _answer_object(body)
        if bundle is None and after.startswith(_SUMMARY_OPEN):
            supplemental = _answer_object(after.removeprefix(_SUMMARY_OPEN).strip())
            if supplemental is not None:
                return json.dumps({'answer': body, 'summary': supplemental['summary']}, ensure_ascii=False)
        decoded = _json_object(body)
        answer = decoded.get('answer') if decoded is not None else (
            body if not body.startswith(('{', '[')) else None)
        if isinstance(answer, str) and answer.strip():
            return json.dumps({
                'answer': answer.strip() + '\n\n> 回答格式异常。已保留正式回答，附加内容未通过校验。',
                'summary': bundle['summary'] if bundle is not None else None,
            }, ensure_ascii=False)
    if not body or after:
        raise AnswerPresentationError('answer_presentation_invalid')
    if answer_format == 'formal-and-core/1' and _json_object(body) is None:
        repaired = _answer_object(body, strict=False)
        if repaired is not None:
            return json.dumps(repaired, ensure_ascii=False)
    return body
