"""Grid-owned artifact path rules for the compatibility application."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from capability_agent.trajectory.artifacts import (
    ArtifactIntegrityError,
    NeutralArtifactPathPolicy,
)


_RESULT_IDENTITY_PATTERN = re.compile(r"^result:sha256:([0-9a-f]{64})$")
_EVIDENCE_IDENTITY_PATTERN = re.compile(r"^evidence:sha256:([0-9a-f]{64})$")
_RESULT_PREFIXES = ("result", "powerflow", "contingency", "contingency-scenario")
_EVIDENCE_LAYOUTS = (
    ("network-facts", "network-fact"),
    ("analysis", "analysis-evidence"),
)


class GridArtifactPathPolicy(NeutralArtifactPathPolicy):
    """Preserve the grid application's existing result/evidence locations."""

    def candidate_paths(
        self, run_root: Path, kind: str, identity: str
    ) -> tuple[Path, ...]:
        if kind == "result":
            match = _RESULT_IDENTITY_PATTERN.fullmatch(identity)
            if match is None:
                raise ArtifactIntegrityError("artifact identity is invalid")
            digest = match.group(1)
            return tuple(
                run_root / "evidence" / "results" / f"{prefix}-{digest}.json"
                for prefix in _RESULT_PREFIXES
            )
        if kind == "evidence":
            match = _EVIDENCE_IDENTITY_PATTERN.fullmatch(identity)
            if match is None:
                raise ArtifactIntegrityError("artifact identity is invalid")
            digest = match.group(1)
            return tuple(
                run_root / "evidence" / directory / f"{prefix}-{digest}.json"
                for directory, prefix in _EVIDENCE_LAYOUTS
            )
        return super().candidate_paths(run_root, kind, identity)

    def identity_for_path(self, kind: str, relative_path: PurePosixPath) -> str:
        if kind == "result":
            if relative_path.is_absolute() or len(relative_path.parts) != 3:
                raise ArtifactIntegrityError("artifact pointer has an invalid relative path")
            root, directory, filename = relative_path.parts
            match = re.fullmatch(
                rf"(?:{'|'.join(_RESULT_PREFIXES)})-([0-9a-f]{{64}})\.json",
                filename,
            )
            if root != "evidence" or directory != "results" or match is None:
                raise ArtifactIntegrityError("artifact pointer has an invalid relative path")
            return f"result:sha256:{match.group(1)}"
        if kind == "evidence":
            if relative_path.is_absolute() or len(relative_path.parts) != 3:
                raise ArtifactIntegrityError("artifact pointer has an invalid relative path")
            root, directory, filename = relative_path.parts
            for expected_directory, prefix in _EVIDENCE_LAYOUTS:
                match = re.fullmatch(rf"{prefix}-([0-9a-f]{{64}})\.json", filename)
                if root == "evidence" and directory == expected_directory and match:
                    return f"evidence:sha256:{match.group(1)}"
            raise ArtifactIntegrityError("artifact pointer has an invalid relative path")
        return super().identity_for_path(kind, relative_path)


__all__ = ["GridArtifactPathPolicy"]
