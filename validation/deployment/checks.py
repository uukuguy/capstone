"""Mechanical sample checks; passing does not establish semantic acceptance."""
import re


def check_answer(expectation, payload):
    text = payload.get("answer", "")
    failures = []
    if not isinstance(text, str) or not text.strip():
        return ["answer_missing"]
    if not re.search(r"[\u4e00-\u9fff]", text):
        failures.append("chinese_final_missing")
    if re.search(r"(?:^|\n)\s*(?:Clarify:|I'll check|Let me check)", text, re.I):
        failures.append("process_prefix")
    results, evidence = payload.get("result_refs", []), payload.get("evidence_refs", [])
    if results and not evidence:
        failures.append("evidence_missing")
    if expectation == "unsupported-generation":
        diagnostics = payload.get("admission", {}).get("diagnostic_codes", [])
        if "task_capability_boundary_verified" not in diagnostics:
            failures.append("generation_boundary_unverified")
    elif expectation not in {
        "model-and-capabilities", "calculation-or-object-clarification",
        "result-or-object-clarification",
    }:
        failures.append("unknown_expectation")
    return failures
