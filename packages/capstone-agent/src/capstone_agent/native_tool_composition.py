"""Application-selected native composition capability. No business semantics."""
import json
from pathlib import Path

COMPOSITION_POLICY = json.loads((Path(__file__).parent / 'resources' / 'tool-composition-policy.json').read_text())
COMPOSITION_TOOLS = ('agent_tools_execute',)
