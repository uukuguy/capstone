"""Bounded task receipts, separate from the Attempt execution phase."""

from collections.abc import Mapping
import re


def _text(value: object, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValueError('task outcome text is invalid')
    return value


def normalize_task_outcome(value: object) -> dict:
    if not isinstance(value, Mapping) or set(value) - {'schema', 'status', 'work', 'diagnostics', 'coverage'} or not {'schema', 'status', 'work', 'diagnostics'}.issubset(value):
        raise ValueError('task outcome fields are invalid')
    if value['schema'] != 'capstone-task-outcome/1' or value['status'] not in {'complete', 'partial', 'unavailable'}:
        raise ValueError('task outcome status is invalid')
    work, diagnostics = value['work'], value['diagnostics']
    if not isinstance(work, (list, tuple)) or len(work) > 32 or not isinstance(diagnostics, (list, tuple)) or len(diagnostics) > 32:
        raise ValueError('task outcome is too large')
    normalized_work = []
    identities = set()
    for item in work:
        if not isinstance(item, Mapping) or set(item) != {'id', 'status', 'summary', 'result_refs', 'evidence_refs'}:
            raise ValueError('task work fields are invalid')
        identity = _text(item['id'], 256)
        if identity in identities or item['status'] not in {'confirmed', 'blocked'}:
            raise ValueError('task work identity or status is invalid')
        identities.add(identity)
        refs = {}
        for name in ('result_refs', 'evidence_refs'):
            values = item[name]
            if not isinstance(values, (list, tuple)) or len(values) > 128:
                raise ValueError('task work references are invalid')
            refs[name] = [_text(ref) for ref in values]
            if len(set(refs[name])) != len(refs[name]) or (item['status'] == 'blocked' and refs[name]):
                raise ValueError('task work references are invalid')
        normalized_work.append({'id': identity, 'status': item['status'], 'summary': _text(item['summary']), **refs})
    normalized_diagnostics = []
    for item in diagnostics:
        if not isinstance(item, Mapping) or set(item) != {'code', 'category', 'stage', 'confirmation', 'summary', 'work_id', 'recovery'}:
            raise ValueError('task diagnostic fields are invalid')
        code = _text(item['code'], 64)
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', code):
            raise ValueError('task diagnostic code is invalid')
        if (item['category'] not in {'input', 'calculation', 'capability', 'invocation', 'service', 'admission', 'storage', 'unknown'}
            or item['stage'] not in {'parse', 'validate', 'execute', 'admit', 'persist'}
            or item['confirmation'] not in {'confirmed', 'unknown'}
            or item['recovery'] not in {'retry', 'provide_input', 'change_scope', 'wait_for_service', 'report_issue', 'none'}
            or item['work_id'] not in identities):
            raise ValueError('task diagnostic classification is invalid')
        normalized_diagnostics.append({**item, 'summary': _text(item['summary'])})
    confirmed = any(item['status'] == 'confirmed' for item in normalized_work)
    blocked = any(item['status'] == 'blocked' for item in normalized_work)
    if (value['status'] == 'partial' and not (confirmed and blocked)) or (value['status'] == 'unavailable' and confirmed) or (value['status'] == 'complete' and blocked):
        raise ValueError('task outcome work contradicts status')
    result = {'schema': value['schema'], 'status': value['status'], 'work': normalized_work, 'diagnostics': normalized_diagnostics}
    if 'coverage' in value:
        coverage = value['coverage']
        if (not isinstance(coverage, Mapping) or set(coverage) != {'requested_scope', 'completed_scenario_count', 'scenario_context_refs', 'full_ranking_allowed'}
            or coverage['requested_scope'] != 'unconfirmed' or coverage['full_ranking_allowed'] is not False
            or type(coverage['completed_scenario_count']) is not int or not 0 < coverage['completed_scenario_count'] <= 128
            or not isinstance(coverage['scenario_context_refs'], (list, tuple))
            or len(coverage['scenario_context_refs']) != coverage['completed_scenario_count']
            or any(not isinstance(ref, str) or not re.fullmatch(r'context:sha256:[0-9a-f]{64}', ref) for ref in coverage['scenario_context_refs'])
            or len(set(coverage['scenario_context_refs'])) != coverage['completed_scenario_count']
            or value['status'] != 'partial'):
            raise ValueError('task coverage is invalid')
        result['coverage'] = dict(coverage)
    return result


def unavailable_outcome(code: str, tool_events: tuple[Mapping, ...]) -> dict:
    """Keep earlier tool blockers and later admission failure without guessing causes."""
    work, diagnostics = [], []
    for index, event in enumerate(event for event in tool_events if event.get('ok') is not True):
        if index >= 31:
            break
        identity = f'tool-{index}'
        work.append({'id': identity, 'status': 'blocked', 'summary': '此调用未取得可接纳的完成结果。', 'result_refs': [], 'evidence_refs': []})
        diagnostics.append({'code': 'tool_outcome_unknown', 'category': 'unknown', 'stage': 'execute', 'confirmation': 'unknown',
            'summary': '工具未返回完整诊断，原因尚未确认；不能据此判断数据不足或程序错误。', 'work_id': identity, 'recovery': 'report_issue'})
        if event.get('error_code') == 'capability_transport_timeout':
            diagnostics[-1].update(code='capability_transport_timeout', category='service', confirmation='confirmed',
                summary='工具调用超过时限。计算是否完成尚未确认，请查看运行过程后再决定是否重试。', recovery='retry')
        if event.get('error_code') == 'reference_admission_rejected':
            work[-1]['summary'] = '此调用返回的引用尚不能用于正式回答。'
            diagnostics[-1].update(code='reference_admission_rejected', category='admission', stage='admit', confirmation='confirmed',
                summary='返回引用未通过当前任务的模型与证据校验；这不等同于工具计算执行失败。', recovery='report_issue')
    work.append({'id': 'answer', 'status': 'blocked', 'summary': '本次指令尚未形成可接纳的完整回答。', 'result_refs': [], 'evidence_refs': []})
    admission = code.startswith('answer_admission') or code == 'capability_required'
    safe_code = code if re.fullmatch(r'[a-z][a-z0-9_]{0,63}', code) else 'tool_outcome_unknown'
    diagnostics.append({'code': safe_code, 'category': 'admission' if admission else 'unknown', 'stage': 'admit' if admission else 'execute',
        'confirmation': 'confirmed' if admission else 'unknown', 'summary': '回答未通过结果与证据接纳，尚不能发布完整结论。' if admission else '执行尚未取得完整结果，原因需要进一步检查。',
        'work_id': 'answer', 'recovery': 'report_issue'})
    return normalize_task_outcome({'schema': 'capstone-task-outcome/1', 'status': 'unavailable', 'work': work, 'diagnostics': diagnostics})
