"""Locate trusted runtime failures without retaining exception text or locals."""
import re


def checked_failure_origin(value: object) -> list[dict]:
    """Admit only source coordinates, never exception text or host paths."""
    if not isinstance(value, list) or len(value) > 8:
        return []
    result = []
    for item in value:
        if (not isinstance(item, dict) or set(item) != {'module', 'function', 'line'}
                or not isinstance(item['module'], str)
                or not re.fullmatch(r'capstone_agent(?:\.[A-Za-z_][A-Za-z0-9_]*)+', item['module'])
                or not isinstance(item['function'], str)
                or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,95}', item['function'])
                or type(item['line']) is not int or not 0 < item['line'] < 1_000_000):
            return []
        result.append(dict(item))
    return result


def native_failure_origin(error: BaseException | None) -> list[dict]:
    result = []
    seen = set()
    while error is not None and id(error) not in seen and len(seen) < 8:
        seen.add(id(error))
        frame = error.__traceback__
        while frame is not None:
            module = frame.tb_frame.f_globals.get('__name__', '')
            function = frame.tb_frame.f_code.co_name
            if (isinstance(module, str) and re.fullmatch(r'capstone_agent(?:\.[A-Za-z_][A-Za-z0-9_]*)+', module)
                    and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,95}', function)):
                result.append({'module': module, 'function': function, 'line': frame.tb_lineno})
            frame = frame.tb_next
        error = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
    return result[-8:]
