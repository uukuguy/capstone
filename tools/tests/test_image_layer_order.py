"""The local images install dependencies before volatile application source."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def instructions(dockerfile: str) -> list[str]:
    logical: list[str] = []
    buffer = ""
    for raw in dockerfile.splitlines():
        stripped = raw.strip()
        if not buffer and (not stripped or stripped.startswith("#")):
            continue
        buffer = f"{buffer} {stripped}".strip() if buffer else stripped
        if buffer.endswith("\\"):
            buffer = buffer[:-1].strip()
            continue
        logical.append(" ".join(buffer.split()))
        buffer = ""
    if buffer:
        logical.append(" ".join(buffer.split()))
    return logical


def index_of(steps: list[str], text: str) -> int:
    matches = [index for index, step in enumerate(steps) if text in step]
    assert matches, text
    return matches[0]


def test_backend_installs_dependencies_pi_and_models_before_source():
    steps = instructions((ROOT / "Dockerfile").read_text())
    volatile = index_of(steps, "COPY packages/ packages/")
    earlier = steps[:volatile]
    assert any("uv sync" in step and "--frozen" in step and "--no-install-project" in step for step in earlier)
    assert any("npm ci --prefix packages/pi-capability-tools" in step for step in earlier)
    assert any("python deploy/install_pinned_pi.py" in step for step in earlier)
    assert any("COPY deploy/local-model-assets/ /opt/capstone-models/" in step for step in earlier)
    assert any("pypsa_model_authority.model_library install --all" in step for step in earlier)
    assert all("COPY packages/ packages/" not in step for step in earlier)


def test_native_scientific_install_precedes_volatile_source_and_backend_image():
    steps = instructions((ROOT / "deploy/general-pi.Dockerfile").read_text())
    scientific = index_of(steps, "uv pip install --system --require-hashes --only-binary :all: -r configs/runtime/native-analysis.lock.txt")
    smoke = index_of(steps, "python tools/native_analysis_smoke.py")
    backend_runtime = index_of(steps, "COPY --from=managed-runtime")
    report = index_of(steps, "/usr/local/bin/capstone-report")
    typescript = index_of(steps, "/opt/pi/node_modules/tsx/dist/cli.mjs /usr/local/bin/tsx")
    executor = index_of(steps, "COPY packages/capstone-agent/src/capstone_agent/general_pi_executor.py")
    guidance = index_of(steps, "COPY packages/capstone-agent/src/capstone_agent/resources/research-guidance.mjs")
    assert scientific < backend_runtime < typescript < report < smoke < executor
    assert scientific < guidance


def test_native_image_includes_every_published_shared_planning_resource():
    from fnmatch import fnmatchcase
    import shlex
    steps = instructions((ROOT / 'deploy/general-pi.Dockerfile').read_text())
    sources = [token for step in steps if step.startswith('COPY ')
               for token in shlex.split(step)[1:-1]]
    resources = ROOT / 'packages/capstone-agent/src/capstone_agent/resources'
    selected = [*resources.glob('task-planning-policy-*.md'), *resources.glob('graph-work-policy-*.json'), resources / 'task-goal-state.mjs', resources / 'task-node-return.mjs', resources / 'research-context-window.mjs', resources / 'tool-result-context.mjs']
    for resource in selected:
        assert any(fnmatchcase(resource.relative_to(ROOT).as_posix(), pattern)
                   for pattern in sources), resource.name


def test_pinned_pi_loader_reads_the_shipped_lock_and_installer():
    probe = ROOT / "deploy/install_pinned_pi.py"
    result = subprocess.run(
        [sys.executable, "-c", """
import importlib.util, inspect, json, sys
from pathlib import Path
root = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("install_pinned_pi", root / "deploy/install_pinned_pi.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
installer, lock_cls = module.load_pi_installer(root)
raw = json.loads((root / "configs/runtime/pi-runtime.lock.json").read_text())
lock = lock_cls.load(root / "configs/runtime/pi-runtime.lock.json")
if lock.package_version != raw["package"]["version"] or lock.commit != raw["source"]["commit"]:
    raise SystemExit("lock mismatch")
found = Path(inspect.getfile(installer)).resolve()
expected = (root / "packages/capability-agent-kernel/src/capability_agent/runtime/installer.py").resolve()
if found != expected:
    raise SystemExit(f"installer path mismatch: {found}")
print("ok")
""", str(ROOT)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
    assert probe.is_file()


def test_local_rebuild_handles_empty_build_options_with_nounset():
    script = (ROOT / 'deploy/rebuild_local.sh').read_text()
    commands = [line for line in script.splitlines() if line.startswith('build_args=(')
                or line.lstrip().startswith('build_args=(build --pull')]
    assert len(commands) == 2
    native = next(line for line in script.splitlines()
                  if line.startswith('"${build_environment[@]}"') and line.endswith('general-pi'))
    probe = '\n'.join(['set -Eu', 'build_options=()', 'build_environment=(env)',
                       'compose=(printf "%s\\n")', *commands,
                       'printf "%s\\n" "${build_args[@]}"', native])
    result = subprocess.run(['/bin/bash', '-c', probe], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        'build', '--pull', 'api', 'worker', 'worker-pypsa', 'worker-native',
        'objects-init', 'build', 'general-pi']
