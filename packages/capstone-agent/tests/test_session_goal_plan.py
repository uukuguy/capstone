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
        "generation": 3, "state": "ready", "attempts_admitted": 0, "max_attempts": 2,
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
    oversized = proposal()
    oversized["steps"].append({"instruction": "Publish.", "expected_result": "Published report."})
    with pytest.raises(ValueError, match="remaining execution budget"):
        bind_initial_goal_plan(
            oversized, thread_id="thr_a", work=work, objective_revision=2, generation=3,
        )


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


def test_goal_review_advances_only_to_the_saved_next_instruction():
    from capstone_agent.session_goal_plan import qualify_planned_review

    plan = {"plan": proposal(), "step_index": 0}
    progress = {"disposition": "continue", "next_instruction": "Repeat the entire goal.",
                "product_refs": ["source.md"]}
    with pytest.raises(ValueError, match="saved next"):
        qualify_planned_review(plan, progress, ("source.md",))
    progress["next_instruction"] = "Run the benchmark."
    reviewed = qualify_planned_review(plan, progress, ("source.md",))
    assert reviewed["step_index"] == 1
    assert reviewed["review_refs"] == ["source.md"]


def test_goal_review_requires_evidence_for_every_criterion():
    from capstone_agent.session_goal_plan import qualify_planned_review

    plan = {"plan": proposal(), "step_index": 1, "review_refs": ["source.md"]}
    progress = {"disposition": "complete", "product_refs": [], "summary": "The source was verified."}
    with pytest.raises(ValueError, match="every criterion"):
        qualify_planned_review(plan, progress, ())
    progress["criteria"] = [{"index": 0, "verdict": "met", "refs": ["unknown.md"]}]
    with pytest.raises(ValueError, match="saved references"):
        qualify_planned_review(plan, progress, ())
    progress["criteria"][0]["refs"] = ["source.md"]
    reviewed = qualify_planned_review(plan, progress, ())
    assert reviewed["criteria"] == progress["criteria"]
    assert reviewed["closure_summary"] == progress["summary"]


def test_review_can_replace_only_unexecuted_steps():
    from capstone_agent.session_goal_plan import qualify_planned_review

    current = {"plan": proposal(), "step_index": 0, "plan_revision": 1}
    progress = {"disposition": "continue", "next_instruction": "Repair source data.",
                "product_refs": ["source.md"],
                "remaining_steps": [
                    {"instruction": "Repair source data.", "expected_result": "Clean source."},
                    {"instruction": "Run the benchmark.", "expected_result": "Saved results."},
                ]}
    updated = qualify_planned_review(current, progress, ("source.md",), objective="Build a benchmark.")
    assert updated["plan_revision"] == 2
    assert updated["plan"]["steps"][0] == current["plan"]["steps"][0]
    assert updated["plan"]["criteria"] == current["plan"]["criteria"]
    assert updated["plan"]["steps"][1]["instruction"] == "Repair source data."
    with pytest.raises(ValueError, match="remaining execution budget"):
        qualify_planned_review(current, progress, ("source.md",), remaining_attempts=1)


def test_final_step_can_add_evidence_backed_repair_without_changing_completed_steps():
    from capstone_agent.session_goal_plan import qualify_planned_review

    current = {"plan": proposal(), "step_index": 1, "plan_revision": 1,
               "review_refs": ["source.md"]}
    progress = {"disposition": "continue", "summary": "Report needs a missing comparison.",
                "next_instruction": "Add the missing comparison.", "product_refs": ["source.md"],
                "remaining_steps": [{"instruction": "Add the missing comparison.",
                                     "expected_result": "Saved comparison."}]}
    revised = qualify_planned_review(current, progress, (), objective="Build a benchmark.", remaining_attempts=1)
    assert revised['plan']['steps'][:2] == current['plan']['steps']
    assert revised['plan']['criteria'] == current['plan']['criteria']
    assert revised['step_index'] == 2
    assert revised['last_decision'] == progress['summary']


def test_provider_objective_echo_does_not_change_the_saved_plan(monkeypatch):
    from capstone_agent import session_goal_plan

    monkeypatch.setattr(session_goal_plan, '_request_plan_model',
        lambda *_: {**proposal(), 'objective': 'Provider echo'})
    assert session_goal_plan.request_initial_plan('Build a benchmark.') == proposal()


def test_plan_request_preserves_required_verification_when_partial_delivery_is_allowed(monkeypatch):
    from capstone_agent import session_goal_plan

    objective = 'Verify the signed approval. Save a partial report if the signature is unavailable.'

    def planner(system, content):
        assert content == objective
        assert 'Keep the original verification requirement as an acceptance criterion' in system
        assert 'judge saved product existence across the whole Goal' in system
        return proposal()

    monkeypatch.setattr(session_goal_plan, '_request_plan_model', planner)
    assert session_goal_plan.request_initial_plan(objective) == proposal()


def test_initial_plan_keeps_literal_checks_and_explicit_numeric_limits(monkeypatch):
    from capstone_agent import session_goal_plan

    objective = 'Write the exact supplied text and one newline. Use at most two local files.'

    def planner(system, content):
        assert content == objective
        assert 'Preserve numeric requirements explicitly stated by the user' in system
        assert 'Compare exact literals directly' in system
        assert 'do not add derived lengths or counts' in system
        return proposal()

    monkeypatch.setattr(session_goal_plan, '_request_plan_model', planner)
    assert session_goal_plan.request_initial_plan(objective) == proposal()


def test_initial_plan_repairs_invalid_criteria_without_user_input(monkeypatch):
    from capstone_agent import session_goal_plan

    requests = []
    objective = 'Build a benchmark.'

    def planner(system, content):
        requests.append((system, content))
        return {**proposal(), 'criteria': [{'text': 'Verified report'}]} if len(requests) == 1 else proposal()

    monkeypatch.setattr(session_goal_plan, '_request_plan_model', planner)
    assert session_goal_plan.request_initial_plan(objective) == proposal()
    assert [content for _, content in requests] == [objective, objective]
    assert 'Goal plan text is required' in requests[1][0]


@pytest.mark.parametrize("disposition", ["complete", "partial", "wait"])
def test_premature_closure_runs_the_next_saved_step(monkeypatch, disposition):
    from capstone_agent import session_goal_plan

    proposed = {
        'schema': 'capstone-work-goal-proposal/1', 'disposition': disposition,
        'summary': 'The source is verified.', 'next_instruction': None,
        'waiting_reason': None, 'product_refs': ['source.md'],
        'criteria': [{'index': 0, 'verdict': 'met', 'refs': ['source.md']}],
    }
    if disposition == "partial":
        proposed["criteria"] = [{"index": 0, "verdict": "unknown", "refs": []}]
    elif disposition == "wait":
        proposed.pop("criteria")
        proposed["waiting_reason"] = "Source signature needs verification."
    monkeypatch.setattr(session_goal_plan, '_request_plan_model', lambda *_: proposed)
    result = session_goal_plan.request_step_review(
        {'objective': 'Build a benchmark.'}, {'plan': proposal()}, {'product_refs': ['source.md']})
    assert result['disposition'] == 'continue'
    assert result['next_instruction'] == 'Run the benchmark.'
    assert result['product_refs'] == ['source.md']
    assert 'criteria' not in result
    assert result["waiting_reason"] is None
    if disposition == "wait":
        assert proposed["waiting_reason"] in result["summary"]


def test_review_request_marks_the_next_saved_step_separately_from_final_criteria(monkeypatch):
    import json
    from capstone_agent import session_goal_plan

    def reviewer(system, content):
        request = json.loads(content)
        assert request['step_index'] == 0
        assert request['next_saved_instruction'] == 'Run the benchmark.'
        assert 'A final criterion that a later step will address is not a blocker' in system
        assert 'Use explicit literals and other inputs supplied in the latest objective' in system
        assert 'continue with a clarified repair instruction' in system
        assert 'Missing user input with no executable work remaining calls for a partial review' in system
        assert 'A verified saved product can satisfy a product-existence criterion' in system
        assert request['prior_saved_evidence_refs'] == ['earlier.txt']
        return {'schema': 'capstone-work-goal-proposal/1', 'disposition': 'continue',
                'summary': 'Source checked', 'next_instruction': 'Run the benchmark again.',
                'waiting_reason': None, 'product_refs': ['source.md']}

    monkeypatch.setattr(session_goal_plan, '_request_plan_model', reviewer)
    result = session_goal_plan.request_step_review(
        {'objective': 'Build a benchmark.'}, {'plan': proposal(), 'review_refs': ['earlier.txt']},
        {'product_refs': ['source.md']})
    assert result['disposition'] == 'continue'
    assert result['next_instruction'] == 'Run the benchmark.'


def test_review_repairs_invalid_criteria_before_settlement(monkeypatch):
    import json
    from capstone_agent import session_goal_plan

    requests = []
    plan = {"plan": proposal(), "step_index": 1, "review_refs": ["report.md"]}
    valid = {"schema": "capstone-work-goal-proposal/1", "disposition": "complete",
             "summary": "Report verified.", "next_instruction": None, "waiting_reason": None,
             "product_refs": [], "criteria": [
                 {"index": index, "verdict": "met", "refs": ["report.md"]}
                 for index, _ in enumerate(plan["plan"]["criteria"])]}

    def reviewer(system, content):
        requests.append(json.loads(content))
        return {**valid, "criteria": []} if len(requests) == 1 else valid

    monkeypatch.setattr(session_goal_plan, "_request_plan_model", reviewer)
    assert session_goal_plan.request_step_review(
        {"objective": "Build a benchmark."}, plan, {"product_refs": []}) == valid
    assert len(requests) == 2
    assert "repair" not in requests[0]
    assert requests[1]["repair"] == "invalid Goal criterion review"


def test_review_accepts_a_continuation_with_admitted_prior_product(monkeypatch):
    import json
    from capstone_agent import session_goal_plan

    requests = []
    valid = {"schema": "capstone-work-goal-proposal/1", "disposition": "continue",
             "summary": "Proceed with the current source.", "next_instruction": "Run the benchmark.",
             "waiting_reason": None, "product_refs": ["current.md"]}

    def reviewer(system, content):
        requests.append(json.loads(content))
        return {**valid, "product_refs": ["prior.md"]}

    monkeypatch.setattr(session_goal_plan, "_request_plan_model", reviewer)
    assert session_goal_plan.request_step_review(
        {"objective": "Build a benchmark."}, {"plan": proposal(), "review_refs": ["prior.md"]},
        {"product_refs": ["current.md"]}) == {**valid, "product_refs": ["prior.md"]}
    assert len(requests) == 1


@pytest.mark.parametrize("step_index, disposition", [(0, "continue"), (1, None)])
def test_review_keeps_saved_products_when_both_model_proposals_are_invalid(monkeypatch, step_index, disposition):
    from capstone_agent import session_goal_plan

    calls = []

    def invalid_review(*args):
        calls.append(args)
        if step_index == 0:
            return {
                "schema": "capstone-work-goal-proposal/1", "disposition": "continue",
                "summary": "Continue with the reported source.", "next_instruction": "Run the benchmark.",
                "waiting_reason": None, "product_refs": ["unavailable.md"],
            }
        return {"unexpected_field": "not a valid proposal"}

    monkeypatch.setattr(session_goal_plan, "_request_plan_model", invalid_review)
    plan = proposal()
    result = session_goal_plan.request_step_review(
        {"objective": "Build a benchmark."}, {"plan": plan, "step_index": step_index},
        {"product_refs": ["report.md"]})
    assert len(calls) == 2
    if disposition == "continue":
        assert result["disposition"] == disposition
        assert result["product_refs"] == ["report.md"]
        assert result["next_instruction"] == plan["steps"][1]["instruction"]
        assert "criteria" not in result
    else:
        assert result is None


def test_partial_goal_review_records_unmet_criteria_and_explanation():
    from capstone_agent.goal_receipts import parse_goal_proposal
    from capstone_agent.session_goal_plan import qualify_planned_review

    bound = {'plan': proposal(), 'step_index': 0, 'review_refs': ['source.md']}
    value = parse_goal_proposal({'schema': 'capstone-work-goal-proposal/1', 'disposition': 'partial',
        'summary': 'The authority did not publish the missing record.', 'next_instruction': None,
        'waiting_reason': None, 'product_refs': ['source.md'],
        'criteria': [{'index': 0, 'verdict': 'unmet', 'refs': []}]})
    reviewed = qualify_planned_review(bound, value, ())
    assert reviewed['criteria'] == value['criteria']
    assert reviewed['closure_summary'] == value['summary']
    value['criteria'][0]['refs'] = ['unadmitted.md']
    with pytest.raises(ValueError, match='saved references'):
        qualify_planned_review(bound, value, ())
