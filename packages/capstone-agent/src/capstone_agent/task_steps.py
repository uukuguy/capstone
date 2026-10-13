"""Host-owned step numbering and tool ownership, scoped to one Attempt."""
from collections.abc import Callable, Mapping
import time
from typing import cast
from capability_agent.application.research_models import TaskProgress

from .harness import normalize_runtime_event


class TaskStepTracker:
    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.steps: dict[str, dict[str, object]] = {}
        self.calls: dict[str, tuple[str, int]] = {}
        self.pending: set[str] = set()
        self.active: str | None = None
        self.pending_failed_steps: set[str] = set()

    def annotate(self, event: Mapping[str, object]) -> dict[str, object]:
        host_fields = {"task_step", "task_step_id", "task_step_number", "step_tool_number", "task_step_error"}
        output = {key: value for key, value in event.items() if key not in host_fields}
        normalized = normalize_runtime_event(output, runtime_mode="capstone")
        payload = normalized["payload"]
        assert isinstance(payload, dict)
        progress = payload.get("task_progress")
        is_progress = payload.get("tool_name") == "agent_task_progress" or payload.get("capability") == "agent_task_progress"
        if is_progress and normalized["event_type"] == "tool_started":
            try:
                requested = TaskProgress.model_validate(event.get("args"))
            except ValueError:
                return output
            if requested.phase != "started":
                return output
            progress = requested.model_dump(mode="json", exclude_none=True)
        if isinstance(progress, dict) and isinstance(progress.get("step_id"), str):
            identity, phase = progress["step_id"], progress.get("phase")
            if phase == "started" and identity not in self.steps and self.active is None:
                self.steps[identity] = {"id": identity, "number": len(self.steps) + 1,
                    "title": progress["text"], "status": "running", "start": self.clock(), "tools": 0}
                self.active = identity
            elif identity == self.active and phase == "completed":
                self.steps[identity]["completion_requested"] = True
                self._finish_if_ready(identity)
            elif identity != self.active or phase not in {"updated", "started"}:
                output["task_step_error"] = "Step transition was not applied; the existing step was retained."
            if identity in self.steps:
                output["task_step"] = self._public(identity)
            return output
        call = payload.get("tool_call_id")
        if not isinstance(call, str) or is_progress:
            return output
        if normalized["event_type"] == "tool_started" and self.active is not None and call not in self.calls:
            state = self.steps[self.active]
            number = cast(int, state["tools"]) + 1
            state["tools"] = number
            self.calls[call] = self.active, number
            self.pending.add(call)
        if call in self.calls:
            identity, number = self.calls[call]
            output.update(task_step_id=identity, task_step_number=self.steps[identity]["number"], step_tool_number=number)
            if normalized["event_type"] == "tool_completed":
                self.pending.discard(call)
                self._finish_if_ready(identity)
                output["task_step"] = self._public(identity)
        return output

    def _finish_if_ready(self, identity: str) -> None:
        state = self.steps[identity]
        if (state.get("completion_requested") and state["status"] == "running"
            and not any(self.calls[call][0] == identity for call in self.pending)):
            state["status"] = "completed"
            state["duration_ms"] = max(0, round((self.clock() - cast(float, state["start"])) * 1000))
            if self.active == identity:
                self.active = None

    def _public(self, identity: str) -> dict[str, object]:
        return {key: value for key, value in self.steps[identity].items()
            if key in {"id", "number", "title", "status", "duration_ms", "response_ms", "first_text_ms", "usage", "finish_reason", "after_failed_steps"}}


class RuntimeStepTracker(TaskStepTracker):
    """Use native execution turns, never model-declared goal completion."""

    def annotate(self, event: Mapping[str, object]) -> dict[str, object]:
        fields = {"task_step", "task_step_id", "task_step_number", "step_tool_number", "task_step_error"}
        output = {key: value for key, value in event.items() if key not in fields}
        if event.get("type") == "runtime_action":
            phase = event.get("phase")
            if phase == "started" and self.active is None:
                number = len(self.steps) + 1
                identity = f"runtime-{number}"
                self.steps[identity] = {"id": identity, "number": number,
                    "title": "生成回复" if event.get('response_kind') == 'reply' else "模型响应",
                    "status": "running", "start": self.clock(), "tools": 0}
                if self.pending_failed_steps:
                    self.steps[identity]["after_failed_steps"] = sorted(self.pending_failed_steps)
                    self.pending_failed_steps.clear()
                self.active = identity
            identity = self.active
            if identity is not None:
                state = self.steps[identity]
                if phase == "response_completed":
                    if not state.get("purpose"):
                        state["title"] = "组织工具调用" if event.get("response_kind") == "tools" else "生成回复"
                    state["response_ms"] = max(0, round((self.clock() - cast(float, state["start"])) * 1000))
                    if isinstance(event.get('usage'), Mapping):
                        usage = cast(Mapping[str, object], event['usage'])
                        counts = {key: usage[key] for key in ('input', 'output', 'cacheRead', 'cacheWrite', 'totalTokens')
                                  if type(usage.get(key)) is int and 0 <= cast(int, usage[key]) <= 100_000_000}
                        if counts:
                            state['usage'] = counts
                elif phase in {"completed", "interrupted"}:
                    state["status"] = "completed"
                    state["finish_reason"] = phase
                    state["duration_ms"] = max(0, round((self.clock() - cast(float, state["start"])) * 1000))
                    self.active = None
                output["task_step"] = self._public(identity)
            return output
        if event.get('type') == 'assistant_process_delta' and event.get('text') and self.active is not None:
            state = self.steps[self.active]
            if 'first_text_ms' not in state:
                state['first_text_ms'] = max(0, round((self.clock() - cast(float, state['start'])) * 1000))
        normalized = normalize_runtime_event(output, runtime_mode="capstone")
        payload = normalized["payload"]
        assert isinstance(payload, dict)
        if normalized["event_type"] == "tool_completed" and payload.get("ok") is False and self.active is not None:
            self.pending_failed_steps.add(self.active)
        if normalized["event_type"] == "tool_started" and self.active is not None:
            arguments = event.get("args")
            purpose = arguments.get("execution_purpose") if isinstance(arguments, dict) else None
            if isinstance(purpose, str) and 0 < len(purpose.strip()) <= 120:
                state = self.steps[self.active]
                if not state.get("call_purpose"):
                    state["title"] = purpose.strip()
                    state["purpose"] = True
                    state["call_purpose"] = True
                    output["task_step"] = self._public(self.active)
        if payload.get("tool_name") == "agent_task_progress" or payload.get("capability") == "agent_task_progress":
            output["runtime_step_tracking"] = True
            if self.active is not None:
                output["task_step_id"] = self.active
                record = payload.get("task_progress")
                if normalized["event_type"] == "tool_started":
                    try:
                        record = TaskProgress.model_validate(event.get("args")).model_dump(mode="json", exclude_none=True)
                    except ValueError:
                        record = None
                if (isinstance(record, dict) and isinstance(record.get("purpose"), str)
                    and not self.steps[self.active].get("call_purpose")):
                    self.steps[self.active]["title"] = record["purpose"]
                    self.steps[self.active]["purpose"] = True
                    output["task_step"] = self._public(self.active)
            return output
        annotated = super().annotate(output)
        if "task_step" in output:
            annotated["task_step"] = output["task_step"]
        return annotated
