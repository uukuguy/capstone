"""Parse explicit browser investigation commands before task dispatch."""
from __future__ import annotations

from dataclasses import dataclass


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
    if operation in {'start', 'run'}:
        if not argument:
            raise ValueError('请输入调查目标或指令。')
    elif operation in {'compare', 'replay'}:
        required = 2 if operation == 'compare' else 1
        if len(argument.split()) != required:
            raise ValueError(f'{operation} 需要 {required} 个引用。')
    elif operation in {'status', 'stop', 'close', 'report'}:
        if argument:
            raise ValueError(f'{operation} 不接受参数。')
    else:
        raise ValueError('可用调试命令为 start、run、status、stop、compare、report、replay、close。')
    return DebugCommand(operation, argument)
