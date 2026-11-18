"""Validate the main Agent's plan before the host admits any plan step."""

SCHEMA = "capstone-session-goal-plan/1"
MAX_PLAN_ENTRIES = 32
MAX_TEXT_BYTES = 4096


def _plan_text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Goal plan text is required")
    value = value.strip()
    if len(value.encode()) > MAX_TEXT_BYTES:
        raise ValueError("Goal plan text exceeds its limit")
    return value


def parse_goal_plan(value: object, *, objective: str) -> dict:
    if (not isinstance(value, dict) or set(value) != {"schema", "criteria", "steps"}
            or value["schema"] != SCHEMA):
        raise ValueError("Invalid Goal plan schema")
    criteria = value["criteria"]
    steps = value["steps"]
    if not isinstance(criteria, list) or not 1 <= len(criteria) <= MAX_PLAN_ENTRIES:
        raise ValueError("Goal plan requires bounded acceptance criteria")
    if not isinstance(steps, list) or not 2 <= len(steps) <= MAX_PLAN_ENTRIES:
        raise ValueError("Goal plan requires multiple bounded instructions")
    instructions = {objective.strip()}
    parsed_steps = []
    for step in steps:
        if not isinstance(step, dict) or set(step) != {"instruction", "expected_result"}:
            raise ValueError("Invalid Goal plan step")
        instruction = _plan_text(step["instruction"])
        if instruction in instructions:
            raise ValueError("Goal plan instructions must be distinct from the objective and each other")
        instructions.add(instruction)
        parsed_steps.append({
            "instruction": instruction,
            "expected_result": _plan_text(step["expected_result"]),
        })
    return {"schema": SCHEMA, "criteria": [_plan_text(item) for item in criteria], "steps": parsed_steps}


def bind_initial_goal_plan(
    proposal: object, *, thread_id: str, work: dict, objective_revision: int, generation: int,
) -> dict:
    """Bind a planner result to the current Work inside the admission transaction."""
    goal = work["goal_mode"]
    if (goal["objective_revision"] != objective_revision
            or goal["generation"] != generation
            or goal["state"] != "ready"
            or goal["attempts_admitted"] != 0
            or "goal_plan" in work):
        raise ValueError("Initial Goal plan is no longer current")
    return {
        "schema": "capstone-session-goal-plan-receipt/1",
        "thread_id": thread_id,
        "work_id": work["work_id"],
        "objective_revision": objective_revision,
        "generation": generation,
        "plan_revision": 1,
        "plan": parse_goal_plan(proposal, objective=goal["objective"]),
    }
