"""Business sample checks, separate from infrastructure readiness."""
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
    if expectation == "model-and-capabilities":
        # Fixture-specific text screening supplements current-run admission;
        # it does not manufacture model facts or prove numerical truth.
        if "39" not in text or not all(word in text for word in ("母线", "线路")):
            failures.append("model_description_missing")
        if not any(word in text for word in ("分析", "潮流", "能力")):
            failures.append("capability_description_missing")
    elif expectation == "unsupported-generation":
        if not any(word in text for word in ("未注册", "不支持", "不可用", "能力缺口", "无法")):
            failures.append("generation_boundary_missing")
        diagnostics = payload.get("admission", {}).get("diagnostic_codes", [])
        if "task_capability_boundary_verified" not in diagnostics:
            failures.append("generation_boundary_unverified")
    elif expectation in {"calculation-or-object-clarification", "result-or-object-clarification"}:
        if not evidence and not any(word in text for word in ("确认", "标识", "歧义", "明确", "不存在", "没有负荷")):
            failures.append("result_or_clarification_missing")
        if not evidence and "注册" in text:
            failures.append("registration_question_sent_to_user")
    else:
        failures.append("unknown_expectation")
    return failures
