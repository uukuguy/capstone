"""Domain-neutral hosted process roots for the Capstone application.

The application package owns the API and worker mode dispatch.  A selected
Domain Pack or Authority adapter supplies the complete Thread assembly through
the factory seam; this module never imports a domain implementation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

from .cli import main as capstone_main
from .thread_application import ThreadApplicationAssembly


HostedApplicationFactory: TypeAlias = Callable[[], ThreadApplicationAssembly]


def _build(factory: HostedApplicationFactory) -> ThreadApplicationAssembly:
    if not callable(factory):
        raise TypeError("hosted application factory must be callable")
    assembly = factory()
    if not isinstance(assembly, ThreadApplicationAssembly):
        raise TypeError("hosted application factory must return ThreadApplicationAssembly")
    return assembly


def run_hosted_api(factory: HostedApplicationFactory) -> int:
    """Run the shared Capstone API with one application-owned assembly."""

    return capstone_main(
        ["serve-hosted"], thread_application=_build(factory),
    )


def run_hosted_worker(factory: HostedApplicationFactory) -> int:
    """Run the shared Capstone worker with one application-owned assembly."""

    return capstone_main(
        ["work-hosted"], thread_application=_build(factory),
    )


__all__ = [
    "HostedApplicationFactory",
    "run_hosted_api",
    "run_hosted_worker",
]
