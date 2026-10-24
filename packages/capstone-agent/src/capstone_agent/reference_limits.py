"""Shared capacity for admitted references and their public transport."""

from .application_capacity import limits

MAX_ATTEMPT_REFERENCES = limits.context_references
# Two reference sets plus a formal answer must fit in the terminal event.
# Large result tables still use projection fragments.
MAX_REFERENCE_EVENT_BYTES = limits.event_bytes


class ReferenceCapacityExceeded(ValueError):
    """The complete lineage exceeds one admitted answer's capacity."""
