"""Stable, protected native runtime installation persistence."""
import json
import re
from pathlib import Path

import pytest


def test_native_image_includes_local_sdk_module_dependencies():
    project = Path(__file__).parents[3]
    resources = project / 'packages/capstone-agent/src/capstone_agent/resources'
    image = (project / 'deploy/general-pi.Dockerfile').read_text()
    destinations = set()
    for line in image.splitlines():
        if not line.startswith('COPY ') or '--from=' in line:
            continue
        *sources, destination = line.split()[1:]
        for pattern in sources:
            for source in project.glob(pattern):
                if source.is_dir():
                    destinations.update(str(Path(destination) / item.relative_to(source))
                                        for item in source.rglob('*') if item.is_file())
                else:
                    destinations.add(str(Path(destination) / source.name)
                                     if destination.endswith('/') else destination)
    pending = ['general-sdk.mjs']
    checked = set()
    while pending:
        name = pending.pop()
        if name in checked:
            continue
        checked.add(name)
        target = f'capstone_agent/resources/{name}'
        assert target in destinations, f'Native image omits {name}'
        source = (resources / name).read_text()
        pending.extend(str(Path(name).parent / dependency) for dependency in
                       re.findall(r"(?:from\s+|import\s*)['\"]\./([^'\"]+\.mjs)['\"]", source))


def seed(root: Path, name: str):
    install = root / 'agent-resources/installs' / name
    install.mkdir(parents=True)
    (install / 'prepared-mcp.json').write_text(json.dumps({'install_id': 'installs/' + name}))
    python = root / 'python/python-fixed/bin/python'
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_text('fixed-interpreter')
    python.chmod(0o755)
    (install / 'venv/bin').mkdir(parents=True)
    (install / 'venv/bin/python').symlink_to(python)
    (root / 'agent-resources/current.json').write_text(json.dumps({'install_id': 'installs/' + name}))


def test_seed_update_keeps_exact_old_install_and_fixed_interpreter(tmp_path):
    from capstone_agent.general_pi_resource_seed import retain_seed
    first, second, retained = (tmp_path / name for name in ('first', 'second', 'retained'))
    seed(first, 'old')
    seed(second, 'new')
    # Image seed links point to the stable deployed target, never a staging path.
    for source, name in ((first, 'old'), (second, 'new')):
        link = source / 'agent-resources/installs' / name / 'venv/bin/python'
        link.unlink()
        link.symlink_to(retained / 'python/python-fixed/bin/python')
    retain_seed(first, retained)
    retain_seed(second, retained)
    assert (retained / 'agent-resources/installs/old/prepared-mcp.json').is_file()
    assert json.loads((retained / 'agent-resources/current.json').read_text())['install_id'] == 'installs/new'
    assert (retained / 'agent-resources/installs/old/venv/bin/python').resolve().read_text() == 'fixed-interpreter'
    assert not (retained / 'python/python-fixed/bin/python').stat().st_mode & 0o222
    assert not (retained / 'agent-resources/installs/old').stat().st_mode & 0o222
    (second / 'python/python-fixed/bin/python').write_text('changed-interpreter')
    with pytest.raises(ValueError, match='retained runtime'):
        retain_seed(second, retained)
    assert (retained / 'python/python-fixed/bin/python').read_text() == 'fixed-interpreter'


def test_seed_never_overwrites_historical_source_bytes(tmp_path):
    from capstone_agent.general_pi_resource_seed import retain_seed
    source, retained = tmp_path / 'seed', tmp_path / 'retained'
    seed(source, 'old')
    link = source / 'agent-resources/installs/old/venv/bin/python'
    link.unlink()
    link.symlink_to(retained / 'python/python-fixed/bin/python')
    retain_seed(source, retained)
    (source / 'agent-resources/installs/old/prepared-mcp.json').write_text('{}')
    with pytest.raises(ValueError, match='retained runtime'):
        retain_seed(source, retained)


def test_compose_protects_persistent_resources_and_starts_seed_entrypoint():
    project = Path(__file__).parents[3]
    compose = (project / 'compose.yaml').read_text()
    service = compose.split('\n  general-pi:\n')[1]
    assert 'read_only: true' in service
    assert 'general-pi-profiles:/var/lib/general-pi/profiles' in service
    assert 'source: general-pi-resources' in service
    assert 'target: /opt/general/.grid-agent/runtime' in service
    assert 'nocopy: true' in service
    assert '  general-pi-resources:' in compose
    assert '  general-pi-profiles:' in compose
    image = (project / 'deploy/general-pi.Dockerfile').read_text()
    assert 'UV_PYTHON_INSTALL_DIR=/opt/general/.grid-agent/runtime/python' in image
    assert 'CMD ["python", "-m", "capstone_agent.general_pi_resource_seed"]' in image


def test_native_analysis_installs_locked_scipy_and_checks_pandas_statistics():
    project = Path(__file__).parents[3]
    image = (project / 'deploy/general-pi.Dockerfile').read_text()
    manifest = json.loads((project / 'configs/runtime/native-analysis.json').read_text())
    roots = {item['requirement'].split('==')[0] for item in manifest['packages']}
    assert {'numpy', 'pandas', 'scipy'} <= roots
    lock = json.loads((project / 'configs/runtime/power-samples.lock.json').read_text())
    assert all(name in lock['dependencies'] for name in ('numpy', 'pandas', 'scipy'))
    assert '--require-hashes --only-binary :all: -r configs/runtime/native-analysis.lock.txt' in image
    assert 'python tools/native_analysis_smoke.py' in image
    smoke = (project / 'tools/native_analysis_smoke.py').read_text()
    assert "method='spearman'" in smoke, 'build must exercise the pandas optional-dependency path'


def test_python_derived_bytecode_is_not_a_retained_resource(tmp_path):
    from capstone_agent.general_pi_resource_seed import retain_seed
    source, retained = tmp_path / 'seed', tmp_path / 'retained'
    seed(source, 'old')
    link = source / 'agent-resources/installs/old/venv/bin/python'
    link.unlink()
    link.symlink_to(retained / 'python/python-fixed/bin/python')
    cache = source / 'python/python-fixed/lib/__pycache__'
    cache.mkdir(parents=True)
    (cache / 'derived.pyc').write_bytes(b'derived-cache')
    retain_seed(source, retained)
    assert not (retained / 'python/python-fixed/lib/__pycache__').exists()
