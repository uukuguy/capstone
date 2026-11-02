import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]

def module():
    path = ROOT / "deploy/user_data_compatibility.py"
    assert path.is_file(), "source-bound descriptor implementation is missing"
    spec = importlib.util.spec_from_file_location("data_contract", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

def context(root):
    for name in ["pyproject.toml", "uv.lock", "packages/backend/pyproject.toml",
                 "packages/backend/src/backend/store.py", "schemas/store.json",
                 "configs/capabilities/backend.json", "deploy/dev_trial_runtime.py"]:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name)
    return root

IMAGES = {"postgres": "postgres@sha256:" + "b" * 64,
          "objects": "objects@sha256:" + "c" * 64}

POLICY_LINK = "packages/capstone-agent/src/capstone_agent/resources/capstone-pi"
POLICY_TARGET = "../../../../../configs/runtime/capstone-pi"


def policy_context(root):
    root = context(root)
    (root / "packages/capstone-agent").mkdir()
    (root / "packages/capstone-agent/pyproject.toml").write_text("policy package")
    policy = root / "configs/runtime/capstone-pi/SYSTEM.md"
    policy.parent.mkdir(parents=True)
    policy.write_text("policy version one")
    link = root / POLICY_LINK
    link.parent.mkdir(parents=True)
    link.symlink_to(POLICY_TARGET, target_is_directory=True)
    return root


def commit_context(root):
    import subprocess
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "commit", "-m", "fixture"], check=True, capture_output=True)
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


@pytest.mark.parametrize('name', ['application-capacity.json', 'execution-guidance.mjs',
                                'runtime-limits.mjs', 'task-record-tools.mjs'])
def test_shared_resource_link_tracks_exact_target_and_rejects_rebinding(tmp_path, name):
    m = module()
    root = context(tmp_path / 'repo')
    for manifest in ['packages/capstone-agent/pyproject.toml', 'packages/pi-capability-tools/package.json']:
        path = root / manifest
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixture manifest')
    link = root / 'packages/capstone-agent/src/capstone_agent/resources' / name
    link.parent.mkdir(parents=True)
    target = root / ('configs/runtime/application-capacity.json' if name.endswith('.json')
                     else 'packages/pi-capability-tools/src/' + name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('first bytes')
    import os
    link.symlink_to(os.path.relpath(target, link.parent))
    revision = commit_context(root)
    first = m.generate_descriptor(root, revision, IMAGES)
    assert m.descriptor_from_git(root, revision, IMAGES) == first
    target.write_text('second bytes')
    second = m.generate_descriptor(root, revision, IMAGES)
    assert second['CAPSTONE_DATA_FORMAT_SHA256'] != first['CAPSTONE_DATA_FORMAT_SHA256']
    updated = commit_context(root)
    assert m.descriptor_from_git(root, updated, IMAGES) == m.generate_descriptor(root, updated, IMAGES)
    link.unlink()
    link.symlink_to('/tmp/unregistered-capstone-resource')
    invalid = commit_context(root)
    for generate in (m.generate_descriptor, m.descriptor_from_git):
        with pytest.raises(ValueError, match='symlink'):
            generate(root, invalid, IMAGES)


def test_registered_policy_link_matches_git_and_tracks_target_content(tmp_path):
    m = module()
    root = policy_context(tmp_path / "repo")
    revision = commit_context(root)
    first = m.generate_descriptor(root, revision, IMAGES)
    assert m.descriptor_from_git(root, revision, IMAGES) == first
    (root / "configs/runtime/capstone-pi/SYSTEM.md").write_text("policy version two")
    second = m.generate_descriptor(root, revision, IMAGES)
    assert second["CAPSTONE_DATA_FORMAT_SHA256"] != first["CAPSTONE_DATA_FORMAT_SHA256"]
    updated_revision = commit_context(root)
    assert m.descriptor_from_git(root, updated_revision, IMAGES) == m.generate_descriptor(root, updated_revision, IMAGES)


@pytest.mark.parametrize("unsafe", ["/tmp/external-policy", "../../../../../schemas", "missing"])
def test_registered_policy_link_rejects_other_targets_in_context_and_git(tmp_path, unsafe):
    m = module()
    root = policy_context(tmp_path / "repo")
    link = root / POLICY_LINK
    link.unlink()
    link.symlink_to(unsafe, target_is_directory=True)
    revision = commit_context(root)
    for generate in (m.generate_descriptor, m.descriptor_from_git):
        with pytest.raises(ValueError, match="symlink"):
            generate(root, revision, IMAGES)


def test_registered_policy_target_rejects_nested_symlink_in_context_and_git(tmp_path):
    m = module()
    root = policy_context(tmp_path / "repo")
    (root / "configs/runtime/capstone-pi/other.md").symlink_to("SYSTEM.md")
    revision = commit_context(root)
    for generate in (m.generate_descriptor, m.descriptor_from_git):
        with pytest.raises(ValueError, match="symlink"):
            generate(root, revision, IMAGES)


@pytest.mark.parametrize("replacement", ["missing", "directory_symlink", "parent_symlink"])
def test_registered_policy_link_requires_a_regular_target_tree(tmp_path, replacement):
    m = module()
    root = policy_context(tmp_path / "repo")
    target = root / "configs/runtime/capstone-pi"
    external = tmp_path / "external-policy"
    target.rename(external)
    if replacement == "directory_symlink":
        target.symlink_to(external, target_is_directory=True)
    elif replacement == "parent_symlink":
        target.parent.rmdir()
        target.parent.symlink_to(tmp_path, target_is_directory=True)
    revision = commit_context(root)
    for generate in (m.generate_descriptor, m.descriptor_from_git):
        with pytest.raises(ValueError, match="symlink"):
            generate(root, revision, IMAGES)

def test_descriptor_is_exact_and_excludes_source_and_ui(tmp_path):
    m = module()
    root = context(tmp_path)
    first = m.generate_descriptor(root, "a" * 40, IMAGES)
    assert set(first) == {"CAPSTONE_DATA_CONTRACT_VERSION", "CAPSTONE_DATA_SOURCE_REVISION", "CAPSTONE_DATA_FORMAT_SHA256"}
    assert first["CAPSTONE_DATA_CONTRACT_VERSION"] == "1"
    (root / "packages/capstone-app/src").mkdir(parents=True)
    (root / "packages/capstone-app/src/ui.ts").write_text("new UI")
    (root / "deploy/dev-trial").mkdir()
    (root / "deploy/dev-trial/capstone.sh").write_text("new manager")
    second = m.generate_descriptor(root, "d" * 40, IMAGES)
    assert first["CAPSTONE_DATA_FORMAT_SHA256"] == second["CAPSTONE_DATA_FORMAT_SHA256"]
    (root / "packages/backend/src/backend/store.py").write_text("changed")
    assert m.generate_descriptor(root, "a" * 40, IMAGES) != first

def test_images_manifests_names_and_missing_inputs_guard(tmp_path):
    m = module()
    root = context(tmp_path)
    first = m.generate_descriptor(root, "a" * 40, IMAGES)
    assert m.generate_descriptor(root, "a" * 40, dict(IMAGES, postgres="postgres:17")) != first
    (root / "uv.lock").unlink()
    with pytest.raises(ValueError, match="required"):
        m.generate_descriptor(root, "a" * 40, IMAGES)

def test_selected_symlink_is_rejected(tmp_path):
    m = module()
    root = context(tmp_path)
    (root / "schemas/link.json").symlink_to(root / "schemas/store.json")
    with pytest.raises(ValueError, match="symlink"):
        m.generate_descriptor(root, "a" * 40, IMAGES)


def test_git_archive_matches_context_without_extraction(tmp_path):
    import subprocess
    m = module()
    root = context(tmp_path / "repo")
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "commit", "-m", "fixture"], check=True, capture_output=True)
    revision = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
    assert m.descriptor_from_git(root, revision, IMAGES) == m.generate_descriptor(root, revision, IMAGES)
    assert before == sorted(str(p.relative_to(root)) for p in root.rglob("*"))
    with pytest.raises(ValueError):
        m.descriptor_from_git(root, "HEAD", IMAGES)


def test_ignored_runtime_dependencies_do_not_enter_digest(tmp_path):
    m = module()
    root = context(tmp_path)
    first = m.generate_descriptor(root, "a" * 40, IMAGES)
    runtime = root / "packages/backend/.venv/lib/package/pyproject.toml"
    runtime.parent.mkdir(parents=True)
    runtime.write_text("ignored installed package")
    assert m.generate_descriptor(root, "a" * 40, IMAGES) == first


def test_missing_backend_manifest_is_rejected(tmp_path):
    m = module()
    root = context(tmp_path)
    (root / "packages/backend/pyproject.toml").unlink()
    with pytest.raises(ValueError, match="required"):
        m.generate_descriptor(root, "a" * 40, IMAGES)
