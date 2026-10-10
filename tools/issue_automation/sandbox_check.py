"""Trusted image entrypoint, run ONLY inside the secret-free Docker sandbox."""
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {"app", "backend"}:
        raise SystemExit("A trusted check profile is required")
    source = Path("/source")
    trusted = Path("/opt/trusted-source")
    if not source.is_dir() or not trusted.is_dir():
        raise SystemExit("This checker runs only in its prepared Docker image")
    workspace = Path("/tmp/capstone-check")
    shutil.copytree(source, workspace)
    # Candidates cannot install or replace dependencies. Their package manifests
    # are not used to choose commands or dependency preparation.
    for package in (trusted / "packages").iterdir():
        destination = workspace / "packages" / package.name
        if destination.is_dir():
            for name in ("node_modules", ".venv"):
                dependency = package / name
                if dependency.is_dir():
                    (destination / name).symlink_to(dependency, target_is_directory=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = ":".join(str(workspace / "packages" / package.name / "src") for package in (trusted / "packages").iterdir() if (package / "src").is_dir())
    env["HOME"] = "/tmp"
    if sys.argv[1] == "app":
        # Invoke the trusted Vitest binary directly, not a candidate npm script.
        argv = ["node", str(trusted / "packages/capstone-app/node_modules/vitest/vitest.mjs"), "run", "--root", str(workspace / "packages/capstone-app")]
    else:
        argv = [str(trusted / "packages/grid-agent/.venv/bin/python"), "-m", "pytest", "packages/capstone-agent/tests", "--ignore=packages/capstone-agent/tests/test_registered_workers.py", "-q", "-p", "no:cacheprovider"]
    return subprocess.run(argv, cwd=workspace, env=env, timeout=3300).returncode


if __name__ == "__main__":
    raise SystemExit(main())
