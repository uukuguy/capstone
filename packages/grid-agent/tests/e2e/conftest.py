from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from grid_agent.runtime.lock import PiRuntimeLock


ROOT = Path(__file__).resolve().parents[4]
SCRIPTED_CLI = (
    'import { spawnSync } from "node:child_process";\n'
    'const result = spawnSync(process.env.PYTHON ?? "python3", '
    '[new URL("./grid-agent-scripted-pi.py", import.meta.url).pathname, '
    '...process.argv.slice(2)], { stdio: "inherit" });\n'
    'process.exit(result.status ?? 1);\n'
)


@pytest.fixture
def scripted_project(tmp_path: Path) -> Callable[[Path], Path]:
    def create(script: Path) -> Path:
        project = tmp_path / "scripted-project"
        shutil.copytree(ROOT / "configs/runtime", project / "configs/runtime")
        extension = project / "packages/pi-grid-tools"
        (extension / "src").mkdir(parents=True)
        for relative in ("package.json", "src/domain-tools.mjs"):
            shutil.copy2(ROOT / "packages/pi-grid-tools" / relative, extension / relative)

        lock = PiRuntimeLock.load(project / "configs/runtime/pi-runtime.lock.json")
        runtime = project / ".grid-agent/runtime/pi"
        source = runtime / "source"
        cli = source / lock.executable
        cli.parent.mkdir(parents=True)
        cli.write_text(SCRIPTED_CLI, encoding="utf-8")
        shutil.copy2(script, cli.with_name("grid-agent-scripted-pi.py"))
        (runtime / "active").write_text(
            f"{source}\n"
            f"commit={lock.commit}\n"
            f"lock_sha256={lock.sha256}\n"
            f"patches_sha256={lock.patches_sha256}\n",
            encoding="utf-8",
        )
        return project

    return create
