"""Compatibility exports for pandapower result projection."""

from pandapower_domain.projection import (
    PandapowerProjectorLookupError,
    PandapowerProjectorRegistry,
    project_domain_result,
)

__all__ = [
    "PandapowerProjectorLookupError",
    "PandapowerProjectorRegistry",
    "project_domain_result",
]
