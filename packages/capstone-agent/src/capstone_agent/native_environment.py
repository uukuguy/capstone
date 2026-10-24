"""Describe only the base environment that passed the image build checks."""
import json
import re
from pathlib import Path

ENVIRONMENT_RECEIPT = Path(__file__).parent.parent / 'runtime-environment.json'


def environment_context(path: Path = ENVIRONMENT_RECEIPT) -> str | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding='utf-8'))
    fields = {'schema', 'python', 'packages', 'commands', 'smoke_capabilities',
              'manifest_sha256', 'lock_sha256'}
    if not isinstance(value, dict) or set(value) != fields or value['schema'] != 'capstone-native-environment/1':
        raise ValueError('Native environment receipt schema is invalid')
    python = value['python']
    if not isinstance(python, dict) or set(python) != {'version', 'implementation'}:
        raise ValueError('Native environment Python receipt is invalid')
    token = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.+\-]*\Z')
    for mapping in (python, value['packages'], value['commands']):
        if not isinstance(mapping, dict) or not mapping or any(
            not isinstance(key, str) or not token.fullmatch(key)
            or not isinstance(item, str) or not token.fullmatch(item)
            for key, item in mapping.items()
        ):
            raise ValueError('Native environment version receipt is invalid')
    checks = value['smoke_capabilities']
    if not isinstance(checks, list) or not checks or any(
        not isinstance(item, str) or not token.fullmatch(item) for item in checks
    ):
        raise ValueError('Native environment smoke receipt is invalid')
    if any(not isinstance(value[key], str) or not re.fullmatch(r'[a-f0-9]{64}', value[key])
           for key in ('manifest_sha256', 'lock_sha256')):
        raise ValueError('Native environment source identity is invalid')
    plot_context = ''
    if 'matplotlib' in value['packages'] and 'chinese_plots' in checks:
        plot_context = (
            '\nChinese plotting was checked with the preinstalled Noto Sans CJK SC font. '
            'Use matplotlib with the Agg backend and that font for static Chinese charts. '
            'Do not download fonts or enumerate installed fonts unless a specific rendering failure requires it. '
        )
    report_context = ''
    if 'capstone-report' in value['commands'] and 'standalone_reports' in checks:
        report_context = (
            '\nFor a standalone HTML report, use capstone-report --spec report.json --output report.html. '
            'Paths are relative to the task working directory. Minimal spec: '
            '{"schema":"capstone-report/1","title":"Report","sections":'
            '[{"id":"results","title":"Results","blocks":'
            '[{"type":"paragraph","text":"Supported findings"},'
            '{"type":"table","csv":"metrics.csv"},'
            '{"type":"figure","path":"chart.png","caption":"Describe the actual chart"}]}]}. '
            'CSV values are displayed unchanged; prepare display units and percentages in the source CSV. '
            'The renderer embeds figures and creates section anchors and figure numbers. '
            'Its receipt and source hashes do not prove factual accuracy: inspect the final report, '
            'check captions against actual charts and claims against verified results. '
            'Native scripts remain available when this block format does not fit the requested output. '
        )
    return (
        'Verified base programming environment (default Python, not a separately selected MCP interpreter). '
        'Use these preinstalled libraries for authorized tasks; do not reinstall them or run a package '
        'inventory unless an observed incompatibility requires it. Skills and MCP permissions are listed '
        'separately. Installed HTTP clients do not grant external network access. '
        + json.dumps(value, ensure_ascii=False, sort_keys=True)
        + plot_context
        + report_context
    )
