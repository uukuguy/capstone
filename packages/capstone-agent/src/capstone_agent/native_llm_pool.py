"""Application-selected text-only reasoning pool. No child tool or source grants."""
import json
from pathlib import Path

LLM_CALL_POOL_POLICY = json.loads(
    (Path(__file__).parent / 'resources' / 'llm-call-pool-policy.json').read_text())
LLM_CALL_POOL_TOOLS = ('agent_llm_submit', 'agent_llm_collect', 'agent_llm_cancel')


def registered_llm_call_pool(value: object) -> bool:
    """Require the exact publication, including integer wire types, without coercion."""
    return (isinstance(value, dict) and set(value) == set(LLM_CALL_POOL_POLICY)
            and all(type(value[key]) is type(expected) and value[key] == expected
                    for key, expected in LLM_CALL_POOL_POLICY.items()))
