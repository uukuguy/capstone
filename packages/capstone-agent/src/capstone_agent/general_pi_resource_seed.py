"""Retain image-built native installs at their original, stable Linux paths."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil


def _merge(source: Path, target: Path, runtime: Path) -> None:
    if source.is_symlink():
        link = os.readlink(source)
        resolved = (target.parent / link).resolve() if not Path(link).is_absolute() else Path(link).resolve()
        if not resolved.is_relative_to(runtime.resolve()):
            raise ValueError('retained runtime link escapes stable installation')
        if target.is_symlink() and os.readlink(target) == link:
            return
        if target.exists() or target.is_symlink():
            raise ValueError('retained runtime link changed')
        target.symlink_to(link)
    elif source.is_dir():
        if target.is_symlink() or (target.exists() and not target.is_dir()):
            raise ValueError('retained runtime directory changed')
        target.mkdir(parents=True, exist_ok=True)
        target.chmod(0o755)
        for child in sorted(source.iterdir()):
            if child.name == '__pycache__' or child.suffix == '.pyc':
                continue
            if child.name == 'current.json' and target == runtime / 'agent-resources':
                continue
            if child.name == 'private' and target.parent == runtime / 'agent-resources/installs':
                continue
            _merge(child, target / child.name, runtime)
    else:
        if target.is_symlink() or (target.exists() and (not target.is_file() or target.read_bytes() != source.read_bytes())):
            raise ValueError('retained runtime bytes changed: ' + str(target.relative_to(runtime)))
        if not target.exists():
            shutil.copyfile(source, target)
            target.chmod(0o555 if source.stat().st_mode & 0o111 else 0o444)


def retain_seed(seed: Path, runtime: Path) -> None:
    """Add selected image installs; never replace any retained interpreter or source.

    The Docker build installs at ``runtime`` before it makes ``seed``. Thus
    absolute venv launchers and shebangs keep exactly the same deployed path.
    A different interpreter at an existing path is an explicit startup failure.
    """
    runtime.mkdir(parents=True, exist_ok=True)
    runtime.chmod(0o755)
    for name in ('python', 'agent-resources'):
        _merge(seed / name, runtime / name, runtime)
    pointer = json.loads((seed / 'agent-resources/current.json').read_text())
    install_id = pointer['install_id']
    if (not isinstance(install_id, str) or not install_id.startswith('installs/')
            or len(Path(install_id).parts) != 2 or '..' in Path(install_id).parts
            or not (runtime / 'agent-resources' / install_id / 'prepared-mcp.json').is_file()):
        raise ValueError('retained runtime selection is invalid')
    destination = runtime / 'agent-resources/current.json'
    temporary = destination.with_name('.current-seed.json')
    temporary.write_text(json.dumps(pointer))
    temporary.chmod(0o444)
    os.replace(temporary, destination)
    for path in runtime.rglob('*'):
        if not path.is_symlink():
            path.chmod(0o555 if path.is_dir() or path.stat().st_mode & 0o111 else 0o444)
    runtime.chmod(0o555)


def main() -> None:
    retain_seed(Path('/opt/general/resource-seed'), Path('/opt/general/.grid-agent/runtime'))
    os.execvp('python', ['python', '-m', 'capstone_agent.general_pi_server'])


if __name__ == '__main__':
    main()
