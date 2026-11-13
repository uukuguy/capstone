"""Check registered local runtime paths without installing runtimes."""

import json
from pathlib import Path

from capability_agent.runtime.extension import PiExtensionLocator
from pandapower_application.gridctl_locator import GridctlLocator


def inspect_local(root: Path) -> dict[str, object]:
    root = root.resolve()
    extension = PiExtensionLocator(
        root, package_name="@capability-agent/pi-tools",
        candidates=(Path("packages/pi-capability-tools"),
                    Path("node_modules/@capability-agent/pi-tools")),
    ).resolve()
    return {"gridctl": str(GridctlLocator(root).resolve()),
            "pi_extension": str(extension), "live_probe": False}


if __name__ == "__main__":
    print(json.dumps(inspect_local(Path(__file__).resolve().parents[1])))
