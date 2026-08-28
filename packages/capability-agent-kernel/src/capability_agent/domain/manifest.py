from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


_ID = re.compile(r"^[a-z][a-z0-9.-]*$")
_PROTOCOL = re.compile(r"^[a-z][a-z0-9.-]*$")
_TOOL_PREFIX = re.compile(r"^[a-z][a-z0-9_]*_$")


class DomainManifestError(ValueError):
    """The selected domain profile is incomplete or incompatible."""


@dataclass(frozen=True, slots=True)
class DomainManifest:
    domain_id: str
    version: str
    display_name: str
    protocol: str
    protocol_version: str
    executable_name: str
    tool_name_prefix: str
    authority_id: str
    capability_contract_root: Path
    system_policy_path: Path
    guide_root: Path

    def __post_init__(self) -> None:
        if not _ID.fullmatch(self.domain_id):
            raise DomainManifestError("domain_id is invalid")
        if not self.version.strip() or not self.display_name.strip():
            raise DomainManifestError("version and display_name are required")
        if not _PROTOCOL.fullmatch(self.protocol):
            raise DomainManifestError("protocol is invalid")
        if not self.protocol_version.strip():
            raise DomainManifestError("protocol_version is required")
        if (
            not self.executable_name
            or "/" in self.executable_name
            or "\\" in self.executable_name
        ):
            raise DomainManifestError("executable_name must be a basename")
        if not _TOOL_PREFIX.fullmatch(self.tool_name_prefix):
            raise DomainManifestError("tool_name_prefix is invalid")
        if not _ID.fullmatch(self.authority_id):
            raise DomainManifestError("authority_id is invalid")

    def assert_resources_present(self) -> None:
        checks = (
            ("capability_contract_root", self.capability_contract_root, "directory"),
            ("system_policy_path", self.system_policy_path, "file"),
            ("guide_root", self.guide_root, "directory"),
        )
        for field, path, kind in checks:
            present = path.is_dir() if kind == "directory" else path.is_file()
            if not present:
                raise DomainManifestError(f"{field} is missing: {path}")

    def assert_environment_compatible(self, environment: Mapping[str, object]) -> None:
        for field, expected in (
            ("protocol", self.protocol),
            ("protocol_version", self.protocol_version),
        ):
            if environment.get(field) != expected:
                raise DomainManifestError(
                    f"environment {field} does not match domain manifest: {expected}"
                )
