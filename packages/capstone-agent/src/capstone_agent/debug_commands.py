"""Parse explicit browser investigation commands before task dispatch."""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from collections.abc import Mapping


investigation_admission = ContextVar("investigation_admission", default=None)


def debug_commands_enabled(environment: Mapping[str, str]) -> bool:
    stage = environment.get('CAPSTONE_DEPLOYMENT_STAGE', 'local')
    return (stage in {'local', 'cloud-development'}
            and environment.get('CAPSTONE_DEBUG_COMMANDS', '1') == '1')


@dataclass(frozen=True)
class DebugCommand:
    operation: str
    argument: str


def parse_debug_command(text: str) -> DebugCommand | None:
    """Return None for ordinary text. Reject invalid reserved commands."""
    words = text.split(maxsplit=2)
    if not text.startswith('/debug') or not words or words[0] != '/debug':
        return None
    operation = words[1] if len(words) > 1 else ''
    argument = words[2].strip() if len(words) > 2 else ''
    if not operation:
        raise ValueError('请输入 /debug 和需要排查的问题。')
    if operation in {'compare', 'replay'}:
        required = 2 if operation == 'compare' else 1
        if len(argument.split()) != required:
            raise ValueError(f'{operation} 需要 {required} 个引用。')
    elif operation in {'status', 'stop', 'close', 'report'}:
        if argument:
            raise ValueError(f'{operation} 不接受参数。')
    else:
        return DebugCommand('investigate', text[len('/debug'):].strip())
    return DebugCommand(operation, argument)
