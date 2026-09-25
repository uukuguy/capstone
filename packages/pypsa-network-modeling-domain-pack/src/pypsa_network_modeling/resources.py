"""Published contract, policy, and guide resources."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

from capability_agent.tools.guide import GuideNotFound


ROOT = Path(__file__).parent / "resources"
CONTRACT_ROOT = ROOT / "capabilities"
POLICY_PATH = ROOT / "policy" / "system-policy.md"
GUIDE_ROOT = ROOT / "guides"


class ModelPolicyProvider:
    def __init__(self) -> None:
        self._digest = hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest()

    def load(self) -> str:
        raw = POLICY_PATH.read_bytes()
        if hashlib.sha256(raw).hexdigest() != self._digest:
            raise ValueError("PyPSA model policy resource changed")
        return raw.decode("utf-8")


class ModelGuideProvider:
    def __init__(self) -> None:
        self._path = GUIDE_ROOT / "SKILL.md"
        self._digest = hashlib.sha256(self._path.read_bytes()).hexdigest()

    def open(self, resource_id: str) -> Mapping[str, object]:
        if resource_id != "overview":
            raise GuideNotFound(resource_id)
        raw = self._path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != self._digest:
            raise ValueError("PyPSA model guide resource changed")
        return {
            "resource_id": "overview", "title": "PyPSA Network Modeling",
            "sha256": self._digest, "text": raw.decode("utf-8"),
        }

    def load(self) -> tuple[Mapping[str, object], ...]:
        return ({key: value for key, value in self.open("overview").items() if key != "text"},)
