"""Install the pinned Pi runtime from its lock without loading the kernel package."""

from __future__ import annotations

import sys
import types
from pathlib import Path


def load_pi_installer(source_root: Path):
    """Load the on-disk installer while the kernel package init stays unloaded.

    ``capability_agent/__init__.py`` imports the application stack. The image
    install step only has the runtime modules it executes.
    """
    root = Path(source_root) / "packages" / "capability-agent-kernel" / "src"
    package = types.ModuleType("capability_agent")
    package.__path__ = [str(root / "capability_agent")]
    package.__package__ = "capability_agent"
    runtime = types.ModuleType("capability_agent.runtime")
    runtime.__path__ = [str(root / "capability_agent" / "runtime")]
    runtime.__package__ = "capability_agent.runtime"
    sys.modules["capability_agent"] = package
    sys.modules["capability_agent.runtime"] = runtime
    from capability_agent.runtime.installer import PiRuntimeInstaller
    from capability_agent.runtime.lock import PiRuntimeLock

    return PiRuntimeInstaller, PiRuntimeLock


def install_pinned_pi(source_root: Path) -> str:
    installer_cls, lock_cls = load_pi_installer(source_root)
    root = Path(source_root)
    lock = lock_cls.load(root / "configs" / "runtime" / "pi-runtime.lock.json")
    command = installer_cls(lock, root / ".grid-agent" / "runtime" / "pi").install()
    return str(command.path)


def main() -> None:
    print(install_pinned_pi(Path("/app")))


if __name__ == "__main__":
    main()
