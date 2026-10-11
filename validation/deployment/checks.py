"""Mechanical sample checks; passing does not establish semantic acceptance."""
import re


def check_professional_route(events):
    """Verify accepted routing only; execution and research remain separate."""
    accepted = [event.payload.get("routing", {}) for event in events
                if event.event_type == "task_route_created"]
    if not accepted:
        accepted = [event.payload for event in events if event.event_type == "turn_route_selected"
                    and event.payload.get("source") == "llm"]
    if len(accepted) != 1:
        return ["professional_route_missing"]
    if accepted[0].get("route") != "professional":
        return ["professional_route_missing"]
    return []


def check_answer(expectation, payload):
    text = payload.get("answer", "")
    failures = []
    if not isinstance(text, str) or not text.strip():
        return ["answer_missing"]
    if not re.search(r"[\u4e00-\u9fff]", text):
        failures.append("chinese_final_missing")
    if re.search(r"(?:^|\n)\s*(?:Clarify:|I'll\b|Let me\b)", text, re.I):
        failures.append("process_prefix")
    results, evidence = payload.get("result_refs", []), payload.get("evidence_refs", [])
    if results and not evidence:
        failures.append("evidence_missing")
    if expectation == "authority-calculation":
        if not results or not evidence or payload.get("admission", {}).get("mode") != "authority_backed":
            failures.append("required_calculation_missing")
    elif expectation == "model-overview":
        # Source-backed topology/metadata can have references without a solver
        # run. Actual calculation calls are checked in the independent tool audit.
        pass
    elif expectation == "source-backed-answer":
        if not evidence:
            failures.append("source_evidence_missing")
    elif expectation == "model-and-capabilities":
        admission = payload.get("admission", {})
        if "task_information_verified" not in admission.get("diagnostic_codes", []):
            failures.append("requested_information_missing")
    elif expectation == "calculation-required":
        admission = payload.get("admission", {})
        if (not results or not evidence or admission.get("mode") != "authority_backed"
            or "task_goal_coverage_verified" not in admission.get("diagnostic_codes", [])):
            failures.append("required_calculation_missing")
    elif expectation == "scenario-execution-required":
        admission = payload.get("admission", {})
        if (not results or not evidence or admission.get("mode") != "authority_backed"
            or not {"task_goal_coverage_verified", "task_goal_coverage_partial"}.intersection(admission.get("diagnostic_codes", []))):
            failures.append("required_scenario_execution_missing")
    elif expectation == "unsupported-generation":
        diagnostics = payload.get("admission", {}).get("diagnostic_codes", [])
        if "task_capability_boundary_verified" not in diagnostics:
            failures.append("generation_boundary_unverified")
    elif expectation not in {
        "model-and-capabilities", "calculation-or-object-clarification",
        "result-or-object-clarification", "authority-calculation", "model-overview", "source-backed-answer",
    }:
        failures.append("unknown_expectation")
    return failures
