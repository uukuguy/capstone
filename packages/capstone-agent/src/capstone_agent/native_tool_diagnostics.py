"""Extract small public diagnostics before truncating native MCP envelopes."""
from collections.abc import Mapping
import json
import re


def tool_execution_diagnostics(result: Mapping) -> Mapping | None:
    """Read declared failure envelopes, never search arbitrary business rows."""
    value: object = result
    for _ in range(12):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                return None
        elif isinstance(value, Mapping):
            gaps = value.get('gaps')
            gap = next((item for item in gaps if isinstance(item, Mapping)), {}) if isinstance(gaps, list) else {}
            scope = gap.get('scope')
            index = scope.get('query_index') if isinstance(scope, Mapping) else None
            data = value.get('data')
            if type(index) is int and isinstance(data, list) and 0 <= index < len(data):
                child = data[index].get('result') if isinstance(data[index], Mapping) else None
                if isinstance(child, Mapping) and child.get('status') in ('error', 'failed'):
                    value = child
                    continue
            provenance = value.get('provenance')
            diagnostic = provenance.get('execution_diagnostics') if isinstance(provenance, Mapping) else None
            if not isinstance(diagnostic, Mapping) and isinstance(scope, Mapping):
                diagnostic = scope.get('diagnostics')
            if isinstance(diagnostic, Mapping):
                return diagnostic
            structured = value.get('structuredContent')
            if isinstance(structured, Mapping):
                value = structured
                continue
            content = value.get('content')
            value = next((part.get('text') for part in content if isinstance(part, Mapping)
                          and part.get('type') == 'text'), None) if isinstance(content, list) else None
        else:
            return None
    return None


def _transport_summary(value: Mapping) -> list[str]:
    diagnostic = tool_execution_diagnostics(value)
    if diagnostic is None or not any(key in diagnostic for key in (
            'transport_phase', 'connection_established', 'request_sent', 'remote_execution_possible')):
        return []
    phase = diagnostic.get('transport_phase')
    parts = [{'connect': '连接阶段失败', 'send': '发送阶段失败', 'receive': '等待响应阶段失败'}
             .get(phase if isinstance(phase, str) else '', '失败阶段未知')]
    if diagnostic.get('connection_established') is False:
        parts.append('连接未建立')
    sent = diagnostic.get('request_sent')
    parts.append('请求已发送' if sent is True else '请求未发送' if sent is False else '发送状态未知')
    state = diagnostic.get('result_state')
    parts.append('未生成结果' if state == 'not_produced' else
                 '网关报告结果已保存' if state == 'saved' else '源端结果未知')
    if diagnostic.get('remote_cancellation_confirmed') is True:
        parts.append('源端取消已确认')
    if state == 'unknown' and (sent is not False or diagnostic.get('remote_execution_possible') is True):
        parts.append('当前操作不可自动重放；先核对源端执行状态')
    elif diagnostic.get('retry_policy') == 'after_connection_restored' or diagnostic.get('transport_phase') == 'connect':
        parts.append('当前操作需先恢复连接；可评估其他独立工作')
    return parts


def structured_tool_diagnostic(result: Mapping) -> str | None:
    value: object = result
    request_ids: list[str] = []
    for _ in range(12):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                return None
        elif isinstance(value, Mapping):
            provenance = value.get('provenance')
            request_id = value.get('request_id') or (
                provenance.get('request_id') if isinstance(provenance, Mapping) else None)
            if isinstance(request_id, str) and request_id not in request_ids:
                request_ids.append(request_id)
            error = value.get('error')
            gaps = value.get('gaps')
            detail = error if isinstance(error, Mapping) else (
                next((gap for gap in gaps if isinstance(gap, Mapping)), {})
                if isinstance(gaps, list) else {})
            # Follow only a referenced failed result, never arbitrary business rows.
            scope = detail.get('scope')
            index = scope.get('query_index') if isinstance(scope, Mapping) else None
            data = value.get('data')
            if type(index) is int and isinstance(data, list) and 0 <= index < len(data):
                item = data[index]
                child = item.get('result') if isinstance(item, Mapping) else None
                if (isinstance(child, Mapping) and child.get('status') == 'error'
                        and (child.get('gaps') or child.get('error'))):
                    value = child
                    continue
            message = detail.get('message') or value.get('message')
            code = detail.get('reason') or detail.get('code') or value.get('code')
            if isinstance(error, str):
                message = error
            if isinstance(message, str) or isinstance(code, str):
                parts = _transport_summary(value) + ([message[:240]] if isinstance(message, str) else [])
                if isinstance(code, str):
                    parts.append('code=' + code[:80])
                scope = detail.get('scope')
                path = detail.get('path') or (scope.get('path') if isinstance(scope, Mapping) else None)
                errors = value.get('validation_errors')
                if path is None and isinstance(errors, list) and errors and isinstance(errors[0], Mapping):
                    path = errors[0].get('path')
                if isinstance(path, str):
                    parts.append('path=' + path[:100])
                for request_id in request_ids:
                    parts.append('request_id=' + request_id[:100])
                # New gateway diagnostics may put these fields in a gap scope.
                # Presence is authoritative: an error alone says nothing about effects.
                scopes = [detail, scope if isinstance(scope, Mapping) else {}, value]
                executed = next((item['executed'] for item in scopes if isinstance(item.get('executed'), bool)), None)
                if executed is not None:
                    parts.append('executed=' + str(executed).lower())
                rejected = next((item['rejected_value'] for item in scopes if 'rejected_value' in item), None)
                if isinstance(rejected, (str, int, float, bool)):
                    protected = re.search(r'(?i)token|password|secret|authorization|api[_ -]?key', str(path))
                    parts.append('rejected_value=' + ('[REDACTED]' if protected else str(rejected)[:80]))
                source = next((item.get('legal_values_source', item.get('allowed_values_source')) for item in scopes
                               if 'legal_values_source' in item or 'allowed_values_source' in item), None)
                if isinstance(source, str):
                    parts.append('legal_values_source=' + source[:120])
                suggestion = next((item.get('suggestion') for item in scopes if isinstance(item.get('suggestion'), str)), None)
                if suggestion and not re.search(r'(?i)token|password|secret|authorization|api[_ -]?key', str(path)):
                    parts.append('suggestion=' + suggestion[:120])
                return '；'.join(parts)
            structured = value.get('structuredContent')
            if isinstance(structured, Mapping) and structured:
                value = structured
                continue
            content = value.get('content')
            value = next((part.get('text') for part in content
                          if isinstance(part, Mapping) and part.get('type') == 'text'), None
                         ) if isinstance(content, list) else None
        else:
            break
    return None
