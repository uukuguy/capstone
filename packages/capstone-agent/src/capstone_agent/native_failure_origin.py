"""Locate trusted runtime failures without retaining exception text or locals."""
import re


def native_failure_origin(error: BaseException) -> list[dict]:
    result = []
    frame = error.__traceback__
    while frame is not None:
        module = frame.tb_frame.f_globals.get('__name__', '')
        function = frame.tb_frame.f_code.co_name
        if (isinstance(module, str) and re.fullmatch(r'capstone_agent(?:\.[A-Za-z_][A-Za-z0-9_]*)+', module)
                and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,95}', function)):
            result.append({'module': module, 'function': function, 'line': frame.tb_lineno})
        frame = frame.tb_next
    return result[-8:]
