"""Validation aliases for the production public Thread catalog projection.

The validation lane must exercise the exact parser used by Web, TUI, and
future clients. Keeping a second wire parser here could let validation pass
while production clients accept a different contract.
"""

from capstone_agent.thread_catalog import (
    ThreadCatalogProfileEntry,
    ThreadCatalogProjection,
    ThreadModelCatalogEntry,
)


ThreadCatalog = ThreadCatalogProjection
ThreadCatalogModel = ThreadModelCatalogEntry
ThreadCatalogProfile = ThreadCatalogProfileEntry


__all__ = ["ThreadCatalog", "ThreadCatalogModel", "ThreadCatalogProfile"]
