"""Preserve per-role local runtime records before Compose replaces containers.

Uses only the selected Compose project's containers and volumes. No credentials
are logged. Original backups remain in the ignored project runtime directory.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def restore(source: Path, target: Path, container_id: str) -> None:
    marker = target / ".capstone-runtime-migration"
    if marker.is_file() and marker.read_text() == container_id:
        return
    if any(target.iterdir()):
        raise RuntimeError("runtime volume is not empty; original container was retained")
    for path in source.iterdir():
        destination = target / path.name
        if path.is_dir() and not path.is_symlink():
            shutil.copytree(path, destination, symlinks=True)
        else:
            shutil.copy2(path, destination, follow_symlinks=False)
    marker.write_text(container_id)


def _docker(args: list[str]) -> str:
    result = subprocess.run(["docker", *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def preserve(compose_file: Path, env_file: Path, backup_root: Path) -> None:
    compose = ["compose", "--env-file", str(env_file), "-f", str(compose_file)]
    # This document contains protected values. Read it in memory; never print it.
    config = json.loads(_docker([*compose, "config", "--format", "json"]))
    migrations = []
    for role in ("api", "worker", "worker-pypsa"):
        container = _docker([*compose, "ps", "--all", "-q", role])
        if not container:
            continue
        info = json.loads(_docker(["inspect", container]))[0]
        mount = next(item for item in config["services"][role]["volumes"] if item["target"] == "/app/runs")
        volume = config["volumes"][mount["source"]]["name"]
        existing = next((item for item in info["Mounts"] if item["Destination"] == "/app/runs"), None)
        if existing:
            if existing.get("Name") != volume:
                raise RuntimeError("runtime volume differs from the selected project's volume")
            continue
        migrations.append((role, info["Id"], volume))
    if not migrations:
        return
    # Freeze all writers before reading any role's workspaces.
    _docker([*compose, "stop", "api", "worker", "worker-pypsa"])
    for role, container, volume in migrations:
        backup = backup_root / container / role
        backup.mkdir(parents=True, exist_ok=True)
        _docker(["cp", f"{container}:/app/runs/.", str(backup)])
        _docker(["volume", "create", "--label", f"com.docker.compose.project={config['name']}",
                 "--label", f"com.docker.compose.volume={role}-runs", volume])
        image = config["services"][role]["image"]
        _docker(["run", "--rm", "--network", "none", "--user", "0", "--entrypoint", "python",
                 "--mount", f"type=volume,source={volume},target=/state",
                 "--mount", f"type=bind,source={backup},target=/source,readonly",
                 image, "/app/deploy/preserve_local_runtime.py", "--restore", "/source", "/state", container])
        print(f"Preserved local runtime records: {role}")


def main() -> None:
    if len(sys.argv) == 5 and sys.argv[1] == "--restore":
        target = Path(sys.argv[3])
        restore(Path(sys.argv[2]), target, sys.argv[4])
        import pwd
        account = pwd.getpwnam("capstone")
        for root, dirs, files in os.walk(target, followlinks=False):
            os.chown(root, account.pw_uid, account.pw_gid)
            for name in dirs + files:
                os.chown(Path(root) / name, account.pw_uid, account.pw_gid, follow_symlinks=False)
    elif len(sys.argv) == 4:
        preserve(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        raise RuntimeError("runtime preservation arguments are invalid")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Subprocess stderr may contain environment values. Do not expose it.
        print("Runtime preservation failed. Original containers and backups were retained.", file=sys.stderr)
        sys.exit(1)
