"""PyPSA hosted worker entry point using the shared Capstone worker host."""

from __future__ import annotations

from capstone_agent.hosted import run_hosted_worker

from .hosted import build_registered_pypsa_thread_application


def main() -> int:
    return run_hosted_worker(build_registered_pypsa_thread_application)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
