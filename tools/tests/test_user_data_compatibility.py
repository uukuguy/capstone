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
