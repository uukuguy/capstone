from pathlib import Path

from capstone_agent.general_pi_resource_seed import prepare_general_runtime


def test_missing_seed_removes_a_retained_pandapower_install(tmp_path: Path):
    runtime = tmp_path / 'runtime'
    install = runtime / 'agent-resources/installs/old/venv'
    install.mkdir(parents=True)
    (install / 'pandapower.pth').write_text('pandapower')
    prepare_general_runtime(tmp_path / 'missing-seed', runtime)
    assert not (runtime / 'agent-resources').exists()
