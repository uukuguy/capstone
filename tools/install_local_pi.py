"""Reuse a verified local Pi runtime, or install the pinned runtime."""

from pathlib import Path

from capability_agent.runtime.installer import PiRuntimeInstaller
from capability_agent.runtime.locator import PiRuntimeLocator, PiRuntimeLocatorError
from capability_agent.runtime.lock import PiRuntimeLock


def ensure_local_pi(root: Path) -> Path:
    root = root.resolve()
    lock = PiRuntimeLock.load(root / "configs/runtime/pi-runtime.lock.json")
    runtime = root / ".grid-agent/runtime/pi"
    locator = PiRuntimeLocator(runtime, runtime_lock=lock)
    try:
        locator.resolve(require_managed=True)
        return locator.probe().path
    except PiRuntimeLocatorError:
        return PiRuntimeInstaller(lock, runtime).install().path


if __name__ == "__main__":
    print(ensure_local_pi(Path(__file__).resolve().parents[1]))
