"""Application-selected model context and compaction budgets, independent of model names."""
from collections.abc import Mapping


def checked_context_policy(value) -> dict:
    fields = {'context_window_tokens', 'max_output_tokens',
              'compaction_reserve_tokens', 'compaction_keep_recent_tokens'}
    if (not isinstance(value, Mapping) or set(value) != fields
            or any(type(v) is not int or not 0 < v <= 9007199254740991 for v in value.values())):
        raise ValueError('Invalid model context policy fields or token counts')
    window = value['context_window_tokens']
    reserve = value['compaction_reserve_tokens']
    if (not value['max_output_tokens'] <= reserve < window
            or value['compaction_keep_recent_tokens'] >= window - reserve):
        raise ValueError('Model context policy must leave space for output, compaction and recent messages')
    return dict(value)


def compaction_settings(policy: dict) -> dict:
    return {'enabled': True, 'reserveTokens': policy['compaction_reserve_tokens'],
            'keepRecentTokens': policy['compaction_keep_recent_tokens']}
