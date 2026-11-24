"""Place an admitted query delivery into the visible answer.

The Domain Pack owns the rows, their order, column units and evidence.
This module checks that shape and writes a markdown table. It does not
calculate, sort or fill in values.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping

_SCHEMA = 'capstone-query-delivery/1'
_REF = re.compile(r'^(?:result|evidence|context|revision):sha256:[0-9a-f]{64}$')
_TABLE_LINE = re.compile(r'^\s*\|.*\|\s*$')
_FORMAL_FENCE = re.compile(r'^```(?:json)?\s*([\s\S]*?)\s*```$', re.IGNORECASE)
_NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,63}$')


def answer_with_query_deliveries(answer: object, deliveries: object, *,
                                 answer_format: str | None = None,
                                 authority_receipts: tuple = ()) -> str:
    """Keep the prose and replace model tables with admitted query tables."""
    if not isinstance(answer, str):
        raise ValueError('query delivery answer is invalid')
    tables = []
    if isinstance(deliveries, (list, tuple)):
        for item in deliveries:
            checked = checked_query_delivery(item)
            if checked is not None:
                checked['evidence_refs'] = list(dict.fromkeys([
                    *checked['evidence_refs'],
                    *(ref for receipt in authority_receipts
                      if tuple(receipt['result_refs']) == (checked['result_ref'],)
                      for ref in receipt['evidence_refs']),
                ]))
                tables.append(_markdown(checked))
    if not tables:
        return answer
    bundle = None
    if answer_format == 'formal-and-core/1':
        raw = answer.strip()
        fenced = _FORMAL_FENCE.fullmatch(raw)
        candidate = fenced.group(1) if fenced else raw
        try:
            bundle = json.loads(candidate)
        except json.JSONDecodeError:
            if candidate.startswith('{'):
                return answer
    bundled = isinstance(bundle, dict) and isinstance(bundle.get('answer'), str)
    draft = bundle['answer'] if bundled else answer
    prose = '\n'.join(line for line in draft.splitlines() if not _TABLE_LINE.match(line)).strip()
    body = '\n\n'.join(tables)
    amended = f'{prose}\n\n{body}' if prose else body
    if bundled:
        return json.dumps({**bundle, 'answer': amended}, ensure_ascii=False)
    return amended


def checked_query_delivery(value: object) -> dict | None:
    """Return a normalized delivery, or None when the shape is not a query table."""
    if not isinstance(value, Mapping) or value.get('schema') != _SCHEMA:
        return None
    columns = value.get('columns')
    rows = value.get('rows')
    evidence = value.get('evidence_refs')
    if (not isinstance(columns, list) or not 1 <= len(columns) <= 32
            or not isinstance(rows, list) or len(rows) > 100
            or not isinstance(evidence, list) or len(evidence) > 16):
        return None
    names = []
    rendered_columns = []
    for column in columns:
        if not isinstance(column, Mapping):
            return None
        name = column.get('name')
        if not isinstance(name, str) or not _NAME.fullmatch(name) or name in names:
            return None
        names.append(name)
        unit = column.get('unit')
        if unit is not None and (not isinstance(unit, str) or not unit.strip() or '|' in unit or '\n' in unit):
            return None
        rendered_columns.append({'name': name, **({'unit': unit} if isinstance(unit, str) else {})})
    rendered_rows = []
    for row in rows:
        if not isinstance(row, Mapping) or any(key not in names for key in row):
            return None
        rendered = {}
        for name in names:
            cell = _cell(row.get(name))
            if cell is None and row.get(name) is not None:
                return None
            rendered[name] = row.get(name)
        rendered_rows.append(rendered)
    if any(not isinstance(item, str) or not _REF.fullmatch(item) for item in evidence):
        return None
    for key in ('row_count', 'returned_row_count', 'offset'):
        if type(value.get(key)) is not int or value[key] < 0:
            return None
    if value['returned_row_count'] != len(rows) or value['row_count'] < len(rows):
        return None
    if value.get('next_offset') is not None and type(value.get('next_offset')) is not int:
        return None
    result_ref, dataset = value.get('result_ref'), value.get('dataset')
    if (not isinstance(result_ref, str) or not _REF.fullmatch(result_ref)
            or not isinstance(dataset, str) or not re.fullmatch(r'result\.res_[a-z0-9_]+', dataset)):
        return None
    return {'schema': _SCHEMA, 'result_ref': result_ref, 'dataset': dataset,
            'columns': rendered_columns, 'rows': rendered_rows,
            'row_count': value['row_count'], 'returned_row_count': value['returned_row_count'],
            'offset': value['offset'], 'next_offset': value.get('next_offset'),
            'evidence_refs': list(evidence)}


def _cell(value: object) -> str | None:
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and math.isfinite(value):
        return format(value, '.12g')
    if isinstance(value, str) and '\n' not in value and '\r' not in value:
        return value.replace('\\', '\\\\').replace('|', '\\|')
    return None


def _markdown(delivery: dict) -> str:
    headers = [f"{column['name']} ({column['unit']})" if 'unit' in column else column['name']
               for column in delivery['columns']]
    names = [column['name'] for column in delivery['columns']]
    lines = ['| ' + ' | '.join(headers) + ' |',
             '| ' + ' | '.join('---' for _ in headers) + ' |']
    for row in delivery['rows']:
        lines.append('| ' + ' | '.join(_cell(row[name]) or '' for name in names) + ' |')
    if delivery['evidence_refs']:
        lines.extend(['', '证据：' + ' '.join(delivery['evidence_refs'])])
    return '\n'.join(lines)
