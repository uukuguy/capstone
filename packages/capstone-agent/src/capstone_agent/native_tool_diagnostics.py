"""Extract small public diagnostics before truncating native MCP envelopes."""
from collections.abc import Mapping
import json


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
                if isinstance(value.get('executed'), bool):
                    parts.append('executed=' + str(value['executed']).lower())
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
