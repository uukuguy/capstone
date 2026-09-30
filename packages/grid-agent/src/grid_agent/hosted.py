"""Capstone hosted composition root for the registered pandapower authority.

The neutral capstone CLI accepts an application-owned model catalog. This
entry point supplies the catalog from the registered grid simulator authority
without making capstone-agent import a domain implementation.
"""

from __future__ import annotations

from capstone_agent.cli import main as capstone_main
from capstone_agent.thread_service import ThreadModelDescriptor
from grid_simulator.engine import Pandapower340Engine
from grid_simulator.models import ModelRegistry


class RegisteredPandapowerThreadCatalog:
    """Resolve exact model revisions from the registered simulator catalog."""

    default_model_id = "ieee39"

    def __init__(self) -> None:
        self._registry = ModelRegistry(Pandapower340Engine())

    def resolve(self, model_id: str | None) -> ThreadModelDescriptor:
        selected = self.default_model_id if model_id is None else model_id
        model = self._registry.get(selected)
        return ThreadModelDescriptor(
            model_id=model.model_id,
            model_revision=self._registry.trusted_revision_ref(model.model_id),
            implementation_family=model.engine,
        )


def main() -> int:
    """Start the shared hosted API with the registered pandapower catalog."""

    return capstone_main(["serve-hosted"], thread_catalog=RegisteredPandapowerThreadCatalog())


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["RegisteredPandapowerThreadCatalog", "main"]
