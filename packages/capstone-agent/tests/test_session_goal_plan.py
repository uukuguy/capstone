import pytest

from capstone_agent.session_goal_plan import parse_goal_plan


def proposal():
    return {
        "schema": "capstone-session-goal-plan/1",
        "criteria": ["The published benchmark includes reproducible results."],
        "steps": [
            {"instruction": "Verify the source data.", "expected_result": "Source receipt."},
            {"instruction": "Run the benchmark.", "expected_result": "Saved results."},
        ],
    }


def test_plan_exposes_a_distinct_first_instruction():
    plan = parse_goal_plan(proposal(), objective="Build a benchmark.")
    assert plan["steps"][0]["instruction"] == "Verify the source data."


@pytest.mark.parametrize("defect", ["raw_objective", "repeated_step", "one_step", "no_criteria", "unknown_field"])
def test_plan_rejects_an_invalid_execution_boundary(defect):
    value = proposal()
    if defect == "raw_objective":
        value["steps"][0]["instruction"] = " Build a benchmark. "
    elif defect == "repeated_step":
        value["steps"][1]["instruction"] = value["steps"][0]["instruction"]
    elif defect == "one_step":
        value["steps"].pop()
    elif defect == "no_criteria":
        value["criteria"] = []
    else:
        value["work_id"] = "model-selected"
    with pytest.raises(ValueError):
        parse_goal_plan(value, objective="Build a benchmark.")


def test_planning_receipt_is_bound_by_the_host():
    from capstone_agent.session_goal_plan import bind_initial_goal_plan

    work = {"work_id": "work_a", "goal_mode": {
        "objective": "Build a benchmark.", "objective_revision": 2,
        "generation": 3, "state": "ready", "attempts_admitted": 0,
    }}
    receipt = bind_initial_goal_plan(
        proposal(), thread_id="thr_a", work=work, objective_revision=2, generation=3,
    )
    assert receipt["thread_id"] == "thr_a"
    assert receipt["work_id"] == "work_a"
    assert receipt["objective_revision"] == 2
    assert receipt["generation"] == 3
    assert receipt["plan_revision"] == 1
    assert receipt["plan"]["steps"][0]["instruction"] == "Verify the source data."


@pytest.mark.parametrize("changed", [
    {"generation": 4}, {"objective_revision": 3}, {"state": "paused"}, {"attempts_admitted": 1},
])
def test_initial_plan_rejects_a_late_result(changed):
    from capstone_agent.session_goal_plan import bind_initial_goal_plan

    work = {"work_id": "work_a", "goal_mode": {
        "objective": "Build a benchmark.", "objective_revision": 2,
        "generation": 3, "state": "ready", "attempts_admitted": 0, **changed,
    }}
    with pytest.raises(ValueError, match="no longer current"):
        bind_initial_goal_plan(
            proposal(), thread_id="thr_a", work=work, objective_revision=2, generation=3,
        )
