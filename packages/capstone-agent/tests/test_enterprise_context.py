"""Work-owned research must not require or inherit a business model."""

from dataclasses import replace
import json

import pytest

from capstone_agent.enterprise_context import TaskContext, WorkBinding
from capstone_agent.attempt_research import AttemptResearch
from capstone_agent.thread_protocol import ModelContextSnapshot


def context(work_id="work_one", *, revision=1, models=()):
    return TaskContext(
        binding=WorkBinding("thr_one", work_id, "research-" + work_id.replace("_", "-")),
        goal_revision=revision, snapshot_id="snapshot_one", model_contexts=models,
    )


def open_research(root, task, attempt):
    return AttemptResearch(root, thread_id=task.binding.thread_id, run_id="run_one",
        attempt_id=attempt, task_context=task,
        is_active=lambda: True, admit_reference=lambda _: False)


def test_model_free_work_restores_research_across_attempts_and_goal_revisions(tmp_path):
    first = open_research(tmp_path, context(), "attempt_one")
    assert first.controller.read() is None
    first.controller.update({"request_id": "save-1", "expected_revision": 0,
                             "changes": {"goal": "Compare supplied documents"}})
    first.close(failed=False)
    resumed = open_research(tmp_path, context(revision=2), "attempt_two")
    assert resumed.research_id == first.research_id
    assert resumed.controller.read().goal == "Compare supplied documents"
    binding = json.loads(resumed.identity_path.read_text())
    assert binding["task_context"]["goal_revision"] == 2
    assert binding["task_context"]["model_contexts"] == []
    assert "baseline_model_context" not in binding
    resumed.close(failed=False)


def test_distinct_work_does_not_inherit_research_even_with_same_model(tmp_path):
    model = ModelContextSnapshot("ctx_one", "model-one", "revision:current", "pandapower", "sel_0")
    first = open_research(tmp_path, context(models=(model,)), "attempt_one")
    first.controller.update({"request_id": "save-1", "expected_revision": 0,
                             "changes": {"goal": "First goal"}})
    first.close(failed=False)
    other = open_research(tmp_path, context("work_two", models=(model,)), "attempt_two")
    assert other.controller.read() is None
    assert other.research_id != first.research_id
    other.close(failed=False)


def test_model_selection_does_not_replace_work_research(tmp_path):
    first = open_research(tmp_path, context(), "attempt_one")
    first.controller.update({"request_id": "save-1", "expected_revision": 0,
                             "changes": {"goal": "Compare sources"}})
    first.close(failed=False)
    model = ModelContextSnapshot("ctx_one", "model-one", "revision:current", "pandapower", "sel_0")
    resumed = open_research(tmp_path, context(models=(model,)), "attempt_two")
    assert resumed.research_id == first.research_id
    assert resumed.controller.read().goal == "Compare sources"
    resumed.close(failed=False)


def test_work_binding_mismatch_fails_before_creating_attempt_files(tmp_path):
    first = open_research(tmp_path, context(), "attempt_one")
    first.close(failed=False)
    wrong = replace(context(), binding=WorkBinding("thr_one", "work_one", "research-other"))
    with pytest.raises(ValueError, match="research identity"):
        open_research(tmp_path, wrong, "attempt_two")
    assert not list(tmp_path.rglob("attempt_two.json"))


def test_task_context_round_trip_and_thread_ownership(tmp_path):
    task = context()
    assert TaskContext.from_document(task.to_document()) == task
    with pytest.raises(ValueError, match="thread"):
        AttemptResearch(tmp_path, thread_id="thr_other", run_id="run_one",
            attempt_id="attempt_one", task_context=task,
            is_active=lambda: True, admit_reference=lambda _: False)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("revision", [True, 0, -1, "1"])
def test_goal_revision_requires_positive_integer(revision):
    with pytest.raises(ValueError, match="goal revision"):
        context(revision=revision)


def test_work_projection_preserves_identity_without_fabricating_model(tmp_path):
    from capstone_agent.harness import normalize_runtime_event
    task = context()
    research = open_research(tmp_path, task, "attempt_one")
    research.controller.update({"request_id": "save-1", "expected_revision": 0,
                               "changes": {"goal": "Compare supplied documents"}})
    projection = research.current_projection()
    normalized = normalize_runtime_event({"type": "research_state", **projection}, runtime_mode="capstone")
    assert normalized["payload"]["task_context"] == task.to_document()
    assert "baseline_model_context" not in normalized["payload"]
    mismatched = replace(task, binding=replace(task.binding, research_id="research-other"))
    with pytest.raises(ValueError, match="research identity"):
        normalize_runtime_event({"type": "research_state", **projection,
                                 "task_context": mismatched.to_document()}, runtime_mode="capstone")
    research.close(failed=False)


def test_work_recovery_requires_existing_terminal_proof(tmp_path):
    first = open_research(tmp_path, context(), "attempt_one")
    first.controller.update({"request_id": "save-1", "expected_revision": 0,
                             "changes": {"goal": "Keep verified observations"}})
    resumed = open_research(tmp_path, context(), "attempt_two")
    assert not resumed.channel.is_active()
    with pytest.raises(RuntimeError, match="verified terminal"):
        resumed.bind_active_check(lambda: True, lambda _: None)
    resumed.bind_active_check(lambda: True, lambda attempt: "interrupted" if attempt == "attempt_one" else None)
    assert resumed.channel.is_active()
    assert resumed.controller.read().goal == "Keep verified observations"
    resumed.close(failed=False)


def test_same_work_token_in_another_thread_has_separate_storage(tmp_path):
    first = open_research(tmp_path, context(), "attempt_one")
    first.close(failed=False)
    task = replace(context(), binding=WorkBinding("thr_other", "work_one", "research-other"))
    second = open_research(tmp_path, task, "attempt_two")
    assert second.identity_path.parent != first.identity_path.parent
    assert second.controller.read() is None
    second.close(failed=False)


def test_legacy_research_is_preserved_beside_new_work(tmp_path):
    model = ModelContextSnapshot("ctx_one", "model-one", "revision:current", "pandapower", "sel_0")
    legacy = AttemptResearch(tmp_path, thread_id="thr_one", run_id="run_one", attempt_id="attempt_old",
        model_context=model, is_active=lambda: True, admit_reference=lambda _: False)
    legacy.controller.update({"request_id": "save-1", "expected_revision": 0,
                             "changes": {"goal": "Historical professional goal"}})
    legacy.close(failed=False)
    saved = legacy.identity_path.read_bytes()
    fresh = open_research(tmp_path, context(models=(model,)), "attempt_new")
    assert fresh.controller.read() is None
    assert legacy.identity_path.read_bytes() == saved
    fresh.close(failed=False)
    restored = AttemptResearch(tmp_path, thread_id="thr_one", run_id="run_one", attempt_id="attempt_old_resume",
        model_context=model, is_active=lambda: True, admit_reference=lambda _: False)
    assert restored.research_id == legacy.research_id
    assert restored.controller.read().goal == "Historical professional goal"
    restored.close(failed=False)


def test_work_keeps_research_across_model_and_run_changes(tmp_path):
    model_a = ModelContextSnapshot("ctx_a", "model-a", "revision:a", "pandapower", "sel_a")
    model_b = ModelContextSnapshot("ctx_b", "model-b", "revision:b", "pypsa", "sel_b")
    first = open_research(tmp_path, context(models=(model_a,)), "attempt_one")
    first.controller.update({"request_id": "save-1", "expected_revision": 0,
                             "changes": {"goal": "Compare available sources"}})
    first.close(failed=False)
    task = replace(context(models=(model_b,)), snapshot_id="snapshot_two")
    resumed = AttemptResearch(tmp_path, thread_id="thr_one", run_id="run_two",
        attempt_id="attempt_two", task_context=task,
        is_active=lambda: True, admit_reference=lambda _: False)
    assert resumed.research_id == first.research_id
    assert resumed.controller.read().goal == "Compare available sources"
    identity = json.loads(resumed.identity_path.read_text())
    assert identity["run_id"] == "run_two"
    assert identity["task_context"]["model_contexts"] == [model_b.to_document()]
    resumed.close(failed=False)


@pytest.mark.parametrize("change", [
    {"extra": "unknown"}, {"model_contexts": {}}, {"resource_refs": "source:one"},
    {"resource_refs": [1]}, {"resource_refs": ["source:one", "source:one"]},
    {"snapshot_id": 1}, {"goal_revision": True},
])
def test_task_context_rejects_invalid_wire_fields(change):
    with pytest.raises(ValueError):
        TaskContext.from_document({**context().to_document(), **change})


@pytest.mark.parametrize("change", [
    {"extra": "unknown"}, {"thread_id": 1}, {"work_id": "../escape"},
    {"research_id": "not_portable"}, {"research_id": None},
])
def test_work_binding_rejects_invalid_wire_identity(change):
    with pytest.raises(ValueError):
        WorkBinding.from_document({**context().binding.to_document(), **change})


def test_task_context_round_trip_with_model_and_resource_references():
    model = ModelContextSnapshot("ctx_one", "model-one", "revision:current", "pandapower", "sel_0")
    task = replace(context(models=(model,)), resource_refs=("source:one@v2", "artifact:two@v1"))
    assert TaskContext.from_document(task.to_document()) == task
    with pytest.raises(ValueError, match="duplicate task model"):
        TaskContext.from_document({**task.to_document(), "model_contexts": [model.to_document()] * 2})


def test_work_context_cannot_be_mixed_with_legacy_selection(tmp_path):
    from capstone_agent.harness import normalize_runtime_event
    model = ModelContextSnapshot("ctx_one", "model-one", "revision:current", "pandapower", "sel_0")
    for kwargs in ({"model_context": model}, {"research_generation": "evt_reset"}):
        with pytest.raises(ValueError, match="mix legacy"):
            AttemptResearch(tmp_path, thread_id="thr_one", run_id="run_one", attempt_id="attempt_one",
                task_context=context(), is_active=lambda: True, admit_reference=lambda _: False, **kwargs)
    assert not list(tmp_path.iterdir())
    with pytest.raises(ValueError, match="mixes work and legacy"):
        normalize_runtime_event({"type": "research_state", "research_id": context().binding.research_id,
            "goal": "Goal", "research_revision": 1, "task_context": context().to_document(),
            "baseline_model_context": model.to_document()}, runtime_mode="capstone")
