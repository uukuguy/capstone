"""Validate the main Agent's plan before the host admits any plan step."""

from contextvars import ContextVar

initial_plan_admission = ContextVar("initial_goal_plan_admission", default=False)

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


def initial_plan_command(thread_id: str, work: dict, proposal: object) -> dict:
    from hashlib import sha256

    receipt = bind_initial_goal_plan(
        proposal, thread_id=thread_id, work=work,
        objective_revision=work["goal_mode"]["objective_revision"],
        generation=work["goal_mode"]["generation"],
    )
    identity = sha256(f'{thread_id}:{work["work_id"]}:{work["revision"]}'.encode()).hexdigest()[:32]
    return {
        "schema": "capstone-command/2", "command_id": f"cmd_plan_{identity}",
        "idempotency_key": f"goal_plan_{identity}", "thread_id": thread_id,
        "kind": "admit_goal_plan",
        "target": {"kind": "work", "id": work["work_id"], "expected_revision": work["revision"]},
        "payload": {"plan": receipt["plan"], "generation": receipt["generation"],
                    "objective_revision": receipt["objective_revision"]},
    }


def request_initial_plan(objective: str) -> dict:
    """Use the registered model without tools to propose a bounded plan."""
    import json
    import httpx

    from .workbench_llm_profiles import ProfileRegistry

    registry = ProfileRegistry()
    profile = registry.resolve(registry.freeze())
    messages = [
        {"role": "system", "content": (
            'Plan the objective for one main Agent in one conversation. '
            'Return a single JSON object with schema "capstone-session-goal-plan/1", '
            'criteria (a list of verifiable acceptance conditions), and steps (a list '
            'of objects with instruction and expected_result). Give at least two '
            'distinct executable instructions in the user’s language. Define a focused '
            'first step. Keep dependencies in order. Do not execute the steps.'
        )},
        {"role": "user", "content": objective},
    ]
    with httpx.Client(timeout=12, trust_env=False, follow_redirects=False) as client:
        with client.stream(
            "POST", profile["base_url"].rstrip("/") + "/chat/completions",
            headers={"Authorization": "Bearer " + profile["key"]},
            json={**profile.get("title_request_options", {}), "model": profile["model"],
                  "max_tokens": 4096, "messages": messages},
        ) as response:
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > 65536:
                    raise ValueError("Goal planner response exceeds its limit")
    choice = json.loads(body)["choices"][0]
    if choice["finish_reason"] != "stop":
        raise ValueError("Goal planner response did not finish")
    return parse_goal_plan(json.loads(choice["message"]["content"]), objective=objective)


def drain_initial_goal_plans(service, *, planner=request_initial_plan) -> int:
    """Process one idle Thread per scan and leave stale plans for the next scan."""
    from datetime import datetime, timezone

    admitted = 0
    for thread_id in service.goal_continuation_candidates(limit=8, include_planning=True):
        snapshot = service.snapshot(thread_id)
        if snapshot.current_attempt is not None:
            continue
        work = next((item for item in snapshot.works if item.get("goal_plan_pending")
                     and item["goal_mode"]["state"] == "ready"), None)
        if work is None:
            continue
        goal = work["goal_mode"]
        expired = datetime.fromisoformat(goal["deadline_at"]) <= datetime.now(timezone.utc)
        try:
            if expired:
                raise ValueError("Goal planning deadline elapsed")
            command = initial_plan_command(thread_id, work, planner(work["goal"]))
        except Exception as error:
            from .native_failure_origin import native_failure_origin
            import logging
            logging.getLogger(__name__).warning(
                "Goal planning failed; thread_id=%s work_id=%s origin=%s",
                thread_id, work["work_id"], native_failure_origin(error),
            )
            command = {
                "schema": "capstone-command/2",
                "command_id": f'cmd_plan_failed_{work["work_id"]}_{work["revision"]}',
                "idempotency_key": f'goal_plan_failed_{work["work_id"]}_{work["revision"]}',
                "thread_id": thread_id, "kind": "fail_goal_plan",
                "target": {"kind": "work", "id": work["work_id"], "expected_revision": work["revision"]},
                "payload": {"reason": "deadline_elapsed" if expired else "goal_planning_failed"},
            }
        receipt = service.submit_initial_goal_plan(command)
        if receipt is not None and receipt.status == "accepted":
            admitted += command["kind"] == "admit_goal_plan"
        break
    return admitted
