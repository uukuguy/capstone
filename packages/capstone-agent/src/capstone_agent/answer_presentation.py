"""Project explicit public text without classifying natural language."""
OPEN = '<capstone-answer>'
CLOSE = '</capstone-answer>'


def public_answer(text: str) -> str:
    if OPEN not in text and CLOSE not in text:
        return text  # Older protocols: do not guess or delete prose.
    if text.count(OPEN) != 1 or text.count(CLOSE) != 1:
        raise ValueError('answer_presentation_invalid')
    _, remainder = text.split(OPEN, 1)
    body, after = remainder.split(CLOSE, 1)
    if not body.strip() or after.strip():
        raise ValueError('answer_presentation_invalid')
    return body.strip()
