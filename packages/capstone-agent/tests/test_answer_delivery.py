from types import SimpleNamespace

import pytest

from capstone_agent.kernel_pi_session import _KernelPiPromptSession


@pytest.mark.parametrize("corrected", ["当前模型包含母线与线路，以下是已取得的数据和可用分析能力。", None])
def test_mixed_opening_continues_same_session_without_discarding_results(corrected):
    draft = "The observations are ready for the requested explanation.\n\n当前模型包含母线与线路，以下是已取得的数据和可用分析能力。"
    calls = []
    traces = []

    def prompt(question, **kwargs):
        calls.append(question)
        return draft if len(calls) == 1 or corrected is None else corrected

    session = _KernelPiPromptSession(SimpleNamespace(timeout_seconds=60, prompt_and_wait=prompt),
        SimpleNamespace(append=lambda kind, payload: traces.append((kind, payload)) or len(traces)), admission=None)
    result = session.prompt_and_wait("介绍当前模型", on_semantic_event=lambda *_: None,
        correlation_id="attempt-1", on_heartbeat=lambda: None)
    assert len(calls) == 2
    assert "Do not run tools" in calls[1]
    assert result == (corrected or draft)
    assert any(kind == "answer_delivery_check" for kind, _ in traces)


@pytest.mark.parametrize("answer", [
    "当前模型包含母线与线路，IEEE-39 可以进行 AC OPF 分析。",
    "This is an English response with the requested model information.",
    "> This is a quoted sentence from the source document.\n\n当前模型包含母线与线路，以下是已取得的数据和可用分析能力。",
])
def test_clean_or_quoted_answer_needs_no_additional_generation(answer):
    calls = []
    def prompt(question, **kwargs):
        calls.append(question)
        return answer
    session = _KernelPiPromptSession(SimpleNamespace(timeout_seconds=60, prompt_and_wait=prompt),
        SimpleNamespace(append=lambda *_: 1), admission=None)
    assert session.prompt_and_wait("说明模型", on_semantic_event=lambda *_: None,
        correlation_id="attempt-1", on_heartbeat=lambda: None) == answer
    assert len(calls) == 1


def test_delivery_correction_failure_does_not_interrupt_completed_business_answer():
    draft = "The observations are ready for the requested explanation.\n\n当前模型包含母线与线路，以下是已取得的数据和可用分析能力。"
    calls = []
    def prompt(question, **kwargs):
        calls.append(question)
        if len(calls) > 1:
            raise TimeoutError("correction unavailable")
        return draft
    session = _KernelPiPromptSession(SimpleNamespace(timeout_seconds=60, prompt_and_wait=prompt),
        SimpleNamespace(append=lambda *_: 1), admission=None)
    assert session.prompt_and_wait("说明模型", on_semantic_event=lambda *_: None,
        correlation_id="attempt-1", on_heartbeat=lambda: None) == draft
    assert len(calls) == 2
