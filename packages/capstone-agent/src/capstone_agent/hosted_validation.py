"""Explicit, cloud-development-only selection and readiness for validation."""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from urllib.parse import urlsplit
from urllib.request import urlopen

from capstone_agent.kernel_pi_session import PreparedKernelSessionBuilder


def validation_mode(environment: Mapping[str, str]) -> str:
    selected = environment.get("CAPSTONE_THREAD_VALIDATION", "")
    if not selected:
        return "normal"
    if selected != "m11":
        raise ValueError("Thread validation selection is invalid")
    if environment.get("CAPSTONE_DEPLOYMENT_STAGE") != "cloud-development":
        raise ValueError("Thread validation requires cloud development")
    return "m11-provider-free"


def select_validation_builder(environment: Mapping[str, str], family: str) -> PreparedKernelSessionBuilder | None:
    if validation_mode(environment) == "normal":
        return None
    if family not in {"pandapower", "pypsa"}:
        raise ValueError("Thread validation family is invalid")
    from validation.thread.m11_session import build_m11_session_builder
    return build_m11_session_builder(family)


def build_validation_status(environment: Mapping[str, str]) -> Callable[[], Mapping[str, object]] | None:
    if validation_mode(environment) == "normal":
        return None
    origins: dict[str, str] = {}
    for entry in environment.get("CAPSTONE_FAMILY_HEALTH_URLS", "").split(","):
        family, separator, origin = entry.partition("=")
        parsed = urlsplit(origin)
        if (not separator or family in origins or family not in {"pandapower", "pypsa"}
                or parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in {"", "/"}):
            raise ValueError("validation family health configuration is invalid")
        origins[family] = origin.rstrip("/")
    if set(origins) != {"pandapower", "pypsa"}:
        raise ValueError("validation requires both family workers")

    def status() -> Mapping[str, object]:
        for family, origin in origins.items():
            with urlopen(origin + "/health", timeout=2) as response:
                raw = response.read(8193)
            if len(raw) > 8192:
                raise ValueError("validation worker health response is too large")
            document = json.loads(raw)
            if (not isinstance(document, dict) or document.get("status") != "ready"
                    or document.get("runtime_mode") != "m11-provider-free"
                    or document.get("implementation_family") != family):
                raise ValueError("validation worker identity or mode mismatch")
        return {"schema": "capstone-m11-readiness/1", "runtime_mode": "m11-provider-free",
                "families": ["pandapower", "pypsa"]}

    return status
