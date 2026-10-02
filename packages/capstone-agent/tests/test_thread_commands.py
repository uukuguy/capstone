from __future__ import annotations

import pytest

from capstone_agent.thread_commands import ThreadCommandFactory


def test_command_factory_builds_model_switch_with_explicit_cursor_and_identity() -> None:
    factory = ThreadCommandFactory("thr_demo_39", "run_001")

    command = factory.switch_model(
        "pypsa39", expected_event_seq=7,
        command_id="cmd_switch_001", idempotency_key="idem_switch_001",
    )

    assert command == {
        "schema": "capstone-command/1",
        "command_id": "cmd_switch_001",
        "idempotency_key": "idem_switch_001",
        "thread_id": "thr_demo_39",
        "run_id": "run_001",
        "kind": "switch_model",
        "expected_event_seq": 7,
        "payload": {"model_id": "pypsa39"},
    }


def test_command_factory_keeps_control_payloads_strict_and_does_not_invent_cursor() -> None:
    factory = ThreadCommandFactory("thr_demo_39", "run_001")

    command = factory.cancel_live_attempt(
        "attempt_004a", expected_event_seq=8,
        command_id="cmd_cancel_001", idempotency_key="idem_cancel_001",
    )

    assert command["payload"] == {"attempt_id": "attempt_004a"}
    assert command["expected_event_seq"] == 8


@pytest.mark.parametrize("model_id", ["", "PyPSA", "pypsa/39/extra"])
def test_command_factory_rejects_invalid_model_ids(model_id: str) -> None:
    factory = ThreadCommandFactory("thr_demo_39", "run_001")

    with pytest.raises(ValueError, match="model_id"):
        factory.switch_model(
            model_id, expected_event_seq=0,
            command_id="cmd_switch_001", idempotency_key="idem_switch_001",
        )


def test_command_factory_accepts_real_hierarchical_model_id() -> None:
    command = ThreadCommandFactory("thr_demo_39", "run_001").switch_model(
        "pypsa-example/scigrid_de", expected_event_seq=0,
        command_id="cmd_switch_001", idempotency_key="idem_switch_001",
    )
    assert command["payload"] == {"model_id": "pypsa-example/scigrid_de"}


def test_command_factory_builds_case_execution_commands_with_strict_payloads() -> None:
    factory = ThreadCommandFactory("thr_case", "run_case")

    start = factory.start_case_execution(
        "case_demo",
        expected_event_seq=3,
        command_id="cmd_start",
        idempotency_key="idem_start",
    )
    retry = factory.retry_case_step(
        "exec_demo",
        step_ordinal=2,
        failed_attempt_id="attempt_failed",
        expected_event_seq=4,
        command_id="cmd_retry",
        idempotency_key="idem_retry",
    )
    cancel = factory.cancel_case_execution(
        "exec_demo",
        expected_event_seq=5,
        command_id="cmd_cancel",
        idempotency_key="idem_cancel",
    )
    resume = factory.resume_case_execution(
        "exec_demo",
        expected_event_seq=6,
        command_id="cmd_resume",
        idempotency_key="idem_resume",
    )

    assert start["payload"] == {
        "case_id": "case_demo",
        "case_version": "1",
        "strategy_id": "sequential_batch",
    }
    assert retry["payload"] == {
        "case_execution_id": "exec_demo",
        "step_ordinal": 2,
        "failed_attempt_id": "attempt_failed",
    }
    assert cancel["payload"] == {"case_execution_id": "exec_demo"}
    assert resume["payload"] == {"case_execution_id": "exec_demo"}
