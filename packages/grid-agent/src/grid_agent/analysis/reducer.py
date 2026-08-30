"""Compatibility exports for the pandapower analysis state reducer.

State transition semantics belong to the pandapower Domain Pack.  The legacy
``grid_agent.analysis`` import remains available for v1.0.1 callers, but this
module deliberately contains no second reducer implementation.
"""

from pandapower_domain.state import (
    ContextTransitionError,
    canonical_state_hash,
    initial_context,
    reduce_context,
)

__all__ = [
    "ContextTransitionError",
    "canonical_state_hash",
    "initial_context",
    "reduce_context",
]
