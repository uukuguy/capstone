"""Hosted worker composition root for the registered pandapower Thread app."""

from __future__ import annotations

from capstone_agent.hosted import run_hosted_worker

from grid_agent.hosted import build_registered_pandapower_thread_application


def main() -> int:
    return run_hosted_worker(build_registered_pandapower_thread_application)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
