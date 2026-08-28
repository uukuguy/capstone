from __future__ import annotations

from pathlib import Path

from capability_agent.tools.guide import GuideDocument, GuideIndex, GuideNotFound


__all__ = ["GuideDocument", "GuideIndex", "GuideNotFound"]


_GRID_GUIDE_ROOT_NAME = "grid-static-analysis"
_GRID_GUIDE_PROTOCOL = "grid-guide-index"


_neutral_load = getattr(
    GuideIndex,
    "_kernel_neutral_load",
    GuideIndex.load.__func__,
)
if not hasattr(GuideIndex, "_kernel_neutral_load"):
    setattr(GuideIndex, "_kernel_neutral_load", _neutral_load)


def _compat_load(
    cls: type[GuideIndex],
    skill_root: Path,
    *,
    protocol: str | None = None,
) -> GuideIndex:
    if protocol is None and Path(skill_root).name == _GRID_GUIDE_ROOT_NAME:
        protocol = _GRID_GUIDE_PROTOCOL
    return _neutral_load(cls, skill_root, protocol=protocol)


if not getattr(GuideIndex, "_grid_compatibility_installed", False):
    GuideIndex.load = classmethod(_compat_load)
    setattr(GuideIndex, "_grid_compatibility_installed", True)
