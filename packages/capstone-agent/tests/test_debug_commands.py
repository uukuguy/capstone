import pytest

from capstone_agent.debug_commands import DebugCommand, debug_commands_enabled, parse_debug_command


@pytest.mark.parametrize(('env', 'enabled'), [
    ({}, True),
    ({'CAPSTONE_DEPLOYMENT_STAGE': 'cloud-development'}, True),
    ({'CAPSTONE_DEBUG_COMMANDS': '0'}, False),
    ({'CAPSTONE_DEBUG_COMMANDS': 'invalid'}, False),
    ({'CAPSTONE_DEPLOYMENT_STAGE': 'user-trial', 'CAPSTONE_DEBUG_COMMANDS': '1'}, False),
    ({'CAPSTONE_DEPLOYMENT_STAGE': 'production'}, False),
])
def test_stage_policy(env, enabled):
    assert debug_commands_enabled(env) is enabled


@pytest.mark.parametrize('text', ['普通指令', '> /debug stop', '```\n/debug stop\n```',
                                  '/debugger stop', '  /debug stop', '日志\n/debug stop'])
def test_ordinary_text(text):
    assert parse_debug_command(text) is None


@pytest.mark.parametrize('text', ['/debug', '/debug bad', '/debug start', '/debug run',
                                  '/debug compare one', '/debug replay one two', '/debug stop now'])
def test_invalid_reserved_command(text):
    with pytest.raises(ValueError):
        parse_debug_command(text)


@pytest.mark.parametrize(('operation', 'argument'), [
    ('start', '比较\n日度和月度'), ('run', '检查原回执'), ('compare', 'old new'),
    ('replay', 'case'), ('status', ''), ('stop', ''), ('close', ''), ('report', '')])
def test_supported_command(operation, argument):
    assert parse_debug_command(f'/debug {operation} {argument}') == DebugCommand(operation, argument)
