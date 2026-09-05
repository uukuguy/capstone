from __future__ import annotations

import shutil
import os
import subprocess
import sys

import pytest

from grid_agent.trajectory.materialize import ProjectionMaterializer
from grid_agent.trajectory.projection_models import AgentTrajectory, ArtifactIndex, BusinessTrajectory, ContextTimeline, ProjectedRun


def test_materialized_cache_rebuild_is_byte_identical(tmp_path) -> None:
    projected = ProjectedRun(analysis_id="analysis-1", source_fingerprint="source-a", agent=AgentTrajectory(analysis_id="analysis-1"), business=BusinessTrajectory(analysis_id="analysis-1"), context=ContextTimeline(analysis_id="analysis-1"), artifacts=ArtifactIndex(analysis_id="analysis-1"))
    materializer = ProjectionMaterializer(tmp_path / ".grid-agent" / "trajectory-cache")
    first = materializer.write(projected, "source-a")
    first_bytes = {path.name: path.read_bytes() for path in first.all_paths}
    shutil.rmtree(first.cache_root)
    second = materializer.write(projected, "source-a")
    assert {path.name: path.read_bytes() for path in second.all_paths} == first_bytes
    assert materializer.load_if_current("analysis-1", "source-a") == projected


def test_materialized_cache_rejects_a_corrupt_typed_envelope(tmp_path) -> None:
    projected = ProjectedRun(analysis_id="analysis-1", source_fingerprint="source-a", agent=AgentTrajectory(analysis_id="analysis-1"), business=BusinessTrajectory(analysis_id="analysis-1"), context=ContextTimeline(analysis_id="analysis-1"), artifacts=ArtifactIndex(analysis_id="analysis-1"))
    materializer = ProjectionMaterializer(tmp_path / "cache")
    paths = materializer.write(projected, "source-a", cache_identity="identity-a")
    paths.projected_run.write_text('{"schema":"trajectory-projection/2.0","identity":"identity-a","payload":{}}', encoding="utf-8")

    assert materializer.load_if_current("analysis-1", "source-a", cache_identity="identity-a") is None


def test_materialized_cache_rejects_an_envelope_for_another_analysis(tmp_path) -> None:
    projected = ProjectedRun(analysis_id="analysis-1", source_fingerprint="source-a", agent=AgentTrajectory(analysis_id="analysis-1"), business=BusinessTrajectory(analysis_id="analysis-1"), context=ContextTimeline(analysis_id="analysis-1"), artifacts=ArtifactIndex(analysis_id="analysis-1"))
    materializer = ProjectionMaterializer(tmp_path / "cache")
    paths = materializer.write(projected, "source-a", cache_identity="identity-a")
    import json
    payload = json.loads(paths.projected_run.read_text(encoding="utf-8"))
    payload["analysis_id"] = "analysis-2"
    paths.projected_run.write_text(json.dumps(payload), encoding="utf-8")

    assert materializer.load_if_current("analysis-1", "source-a", cache_identity="identity-a") is None


def test_materializer_held_directory_fd_survives_post_open_leaf_swap(tmp_path, monkeypatch) -> None:
    projected = ProjectedRun(analysis_id="analysis-1", source_fingerprint="source-a", agent=AgentTrajectory(analysis_id="analysis-1"), business=BusinessTrajectory(analysis_id="analysis-1"), context=ContextTimeline(analysis_id="analysis-1"), artifacts=ArtifactIndex(analysis_id="analysis-1"))
    cache = tmp_path / "cache"
    materializer = ProjectionMaterializer(cache)
    materializer.write(projected, "source-a", cache_identity="identity-a")
    leaf = materializer._paths("analysis-1", "identity-a").cache_root
    outside = tmp_path / "run"
    outside.mkdir()
    import grid_agent.trajectory.materialize as module
    original = module._atomic_write_at
    swapped = False

    def swap_then_write(directory, name, value):
        nonlocal swapped
        if not swapped:
            saved = tmp_path / "saved"
            leaf.rename(saved)
            leaf.symlink_to(outside, target_is_directory=True)
            swapped = True
        original(directory, name, value)

    monkeypatch.setattr(module, "_atomic_write_at", swap_then_write)
    materializer.write(projected, "source-a", cache_identity="identity-a")

    assert not (outside / "projected-run.json").exists()


@pytest.mark.parametrize("operation", ["load", "write"])
def test_cache_root_ancestor_swap_is_not_followed(tmp_path, monkeypatch, operation):
    projected = ProjectedRun(analysis_id="analysis-1", source_fingerprint="source-a", agent=AgentTrajectory(analysis_id="analysis-1"), business=BusinessTrajectory(analysis_id="analysis-1"), context=ContextTimeline(analysis_id="analysis-1"), artifacts=ArtifactIndex(analysis_id="analysis-1"))
    ancestor = tmp_path / "cache-parent"
    materializer = ProjectionMaterializer(ancestor / "cache")
    materializer.write(projected, "source-a")
    run = tmp_path / "run"
    run.mkdir()
    real_open = os.open
    swapped = False

    def swapping_open(path, flags, *args, **kwargs):
        nonlocal swapped
        if path == "cache-parent" and not swapped:
            ancestor.rename(tmp_path / "original-cache-parent")
            ancestor.symlink_to(run, target_is_directory=True)
            swapped = True
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", swapping_open)
    if operation == "load":
        assert materializer.load_if_current("analysis-1", "source-a") is None
    else:
        with pytest.raises(OSError):
            materializer.write(projected, "source-a")
    assert swapped
    assert list(run.iterdir()) == []


def test_cache_fifo_without_writer_returns_miss_without_blocking(tmp_path):
    materializer = ProjectionMaterializer(tmp_path / "cache")
    path = materializer._paths("analysis-1", "source-a").projected_run
    path.parent.mkdir(parents=True)
    os.mkfifo(path)
    result = subprocess.run(
        [sys.executable, "-c",
         "from pathlib import Path; from grid_agent.trajectory.materialize import ProjectionMaterializer; "
         "import sys; assert ProjectionMaterializer(Path(sys.argv[1])).load_if_current('analysis-1','source-a') is None",
         str(materializer.cache_root)],
        capture_output=True, text=True, timeout=3,
    )
    assert result.returncode == 0, result.stderr


def test_cache_file_symlink_is_rejected(tmp_path):
    projected = ProjectedRun(analysis_id="analysis-1", source_fingerprint="source-a", agent=AgentTrajectory(analysis_id="analysis-1"), business=BusinessTrajectory(analysis_id="analysis-1"), context=ContextTimeline(analysis_id="analysis-1"), artifacts=ArtifactIndex(analysis_id="analysis-1"))
    materializer = ProjectionMaterializer(tmp_path / "cache")
    paths = materializer.write(projected, "source-a")
    saved = tmp_path / "saved-envelope.json"
    paths.projected_run.rename(saved)
    paths.projected_run.symlink_to(saved)
    assert materializer.load_if_current("analysis-1", "source-a") is None


@pytest.mark.parametrize("unsafe", ["", ".", "..", "/tmp/key", "a/b", "a\\b"])
def test_materializer_rejects_unsafe_cache_path_segments(tmp_path, unsafe: str) -> None:
    materializer = ProjectionMaterializer(tmp_path / ".grid-agent" / "trajectory-cache")
    projected = ProjectedRun(analysis_id="analysis-1", source_fingerprint="source-a", agent=AgentTrajectory(analysis_id="analysis-1"), business=BusinessTrajectory(analysis_id="analysis-1"), context=ContextTimeline(analysis_id="analysis-1"), artifacts=ArtifactIndex(analysis_id="analysis-1"))

    with pytest.raises(ValueError, match="cache path segment"):
        materializer.write(projected.model_copy(update={"analysis_id": unsafe}), "source-a")

    with pytest.raises(ValueError, match="cache path segment"):
        materializer.load_if_current("analysis-1", unsafe)
