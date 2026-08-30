from __future__ import annotations

from pathlib import Path

from pandapower_domain.acceptance import PandapowerAcceptanceProfile


def test_acceptance_declares_real_business_files_and_task10_scripted_cases() -> None:
    profile = PandapowerAcceptanceProfile()

    provider_cases = profile.provider_cases()
    scripted_cases = profile.scripted_cases()

    paths = {case.instructions_path for case in provider_cases}
    assert paths == {
        Path("validation/questions/task.md.txt"),
        Path("validation/questions/test.md.txt"),
    }
    assert {case.case_id for case in scripted_cases} >= {
        "task10-context-reuse",
        "task10-answer-audit",
        "task10-output-contract",
    }
