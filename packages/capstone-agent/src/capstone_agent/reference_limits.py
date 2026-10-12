"""Shared capacity for admitted references and their public transport."""

MAX_ATTEMPT_REFERENCES = 1024
# Two reference sets plus a formal answer must fit in the terminal event.
# Large result tables still use projection fragments.
MAX_REFERENCE_EVENT_BYTES = 2 * 1024 * 1024


class ReferenceCapacityExceeded(ValueError):
    """The complete lineage exceeds one admitted answer's capacity."""
