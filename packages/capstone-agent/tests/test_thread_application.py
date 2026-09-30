from __future__ import annotations

from capstone_agent.thread_application import ApplicationPiRuntimeFactory
from capstone_agent.thread_service import AttemptClaim
from capstone_agent.thread_protocol import AttemptSnapshot


class _Session:
    def start(self) -> None:
        return None

    def prompt_and_wait(self, question: str, **kwargs: object) -> str:
        del question, kwargs
        return "answer"

    def stop(self) -> None:
        return None


def _claim() -> AttemptClaim:
    return AttemptClaim(
        thread_id="thr_application", run_id="run_application",
        attempt=AttemptSnapshot("turn_1", "attempt_1", "running", "ctx_ieee39"),
        kind="send_ordinary", instruction="inspect", model_context_id="ctx_ieee39",
        selection_revision="sel_0", lease_token="lease_1",
    )


def test_application_factory_wraps_injected_session_as_harness_runtime() -> None:
    received: list[AttemptClaim] = []
    factory = ApplicationPiRuntimeFactory(
        lambda claim: received.append(claim) or _Session(), runtime_mode="capstone",
    )

    runtime = factory(_claim())
    runtime.start()
    assert runtime.prompt("inspect", on_event=lambda _event: None) == "answer"
    runtime.stop()
    assert received[0].attempt.attempt_id == "attempt_1"
