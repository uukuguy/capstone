"""Hosted worker composition root for the registered pandapower Thread app."""

from __future__ import annotations

import os
from dataclasses import replace

from capstone_agent.hosted import run_hosted_worker

from grid_agent.hosted import build_registered_pandapower_thread_application


def build_worker_application():
    application = build_registered_pandapower_thread_application()
    if os.environ.get("CAPSTONE_FEDERATED_CATALOG_CONTEXT", "").lower() != "true":
        return application
    from capstone_agent.federated_hosted import build_federated_thread_catalog

    return replace(
        application,
        catalog_context=build_federated_thread_catalog().to_document(),
    )


def main() -> int:
    return run_hosted_worker(build_worker_application)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_worker_application", "main"]
