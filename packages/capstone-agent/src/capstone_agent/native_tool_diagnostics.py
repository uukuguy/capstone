"""Extract small public diagnostics before truncating native MCP envelopes."""
from collections.abc import Mapping
import json
import re


def structured_tool_diagnostic(result: Mapping) -> str | None:
    value: object = result
    for _ in range(12):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                return None
        elif isinstance(value, Mapping):
            error = value.get('error')
            gaps = value.get('gaps')
            detail = error if isinstance(error, Mapping) else (
                next((gap for gap in gaps if isinstance(gap, Mapping)), {})
                if isinstance(gaps, list) else {})
            message = detail.get('message') or value.get('message')
            code = detail.get('reason') or detail.get('code') or value.get('code')
            if isinstance(error, str):
                message = error
            if isinstance(message, str) or isinstance(code, str):
                parts = [message[:240]] if isinstance(message, str) else []
                if isinstance(code, str):
                    parts.append('code=' + code[:80])
                scope = detail.get('scope')
                path = detail.get('path') or (scope.get('path') if isinstance(scope, Mapping) else None)
                errors = value.get('validation_errors')
                if path is None and isinstance(errors, list) and errors and isinstance(errors[0], Mapping):
                    path = errors[0].get('path')
                if isinstance(path, str):
                    parts.append('path=' + path[:100])
                provenance = value.get('provenance')
                request_id = value.get('request_id') or (
                    provenance.get('request_id') if isinstance(provenance, Mapping) else None)
                if isinstance(request_id, str):
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
