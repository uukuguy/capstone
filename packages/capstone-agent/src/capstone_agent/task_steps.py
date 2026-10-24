"""Host-owned step numbering and tool ownership, scoped to one Attempt."""
from collections.abc import Callable, Mapping
from hashlib import sha256
import time
from typing import cast
from capability_agent.application.research_models import TaskProgress

from .harness import normalize_runtime_event, _precheck_task_progress
from .native_research_bridge import CYCLE_CONTROL_TOOLS


class TaskStepTracker:
    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.steps: dict[str, dict[str, object]] = {}
        self.calls: dict[str, tuple[str, int]] = {}
        self.pending: set[str] = set()
        self.cycle_calls: set[str] = set()
        self.active: str | None = None
        self.pending_failed_steps: set[str] = set()
        self.response_started: tuple[float, str | None] | None = None
        self.response_seconds: dict[str, float] = {}

    def annotate(self, event: Mapping[str, object]) -> dict[str, object]:
        host_fields = {"task_step", "task_step_id", "task_step_number", "step_tool_number", "task_step_error"}
        output = {key: value for key, value in event.items() if key not in host_fields}
        if event.get('type') == 'runtime_action':
            # Only parent model boundaries measure response time. Objective
            # execution spans tools and many turns; its start is not a model
            # request start. Fix ownership before control tools change steps.
            if event.get('subordinate') is True:
                return output
            phase = event.get('phase')
            if phase == 'started' and self.response_started is None:
                self.response_started = self.clock(), self.active
            elif phase == 'response_completed' and self.response_started is not None:
                started, identity = self.response_started
                self.response_started = None
                if identity is not None:
                    elapsed = max(0, self.clock() - started)
                    self.response_seconds[identity] = self.response_seconds.get(identity, 0) + elapsed
                    self.steps[identity]['response_ms'] = round(self.response_seconds[identity] * 1000)
                    output['task_step'] = self._public(identity)
            elif phase in {'completed', 'interrupted'}:
                # Without a response-completed boundary the interval is not
                # known: this terminal may arrive after tool execution. Keep
                # previous measured responses and never count the tool wait.
                self.response_started = None
            return output
        normalized = normalize_runtime_event(output, runtime_mode="capstone")
        payload = normalized["payload"]
        assert isinstance(payload, dict)
        progress = payload.get("task_progress")
        is_progress = payload.get("tool_name") == "agent_task_progress" or payload.get("capability") == "agent_task_progress"
        if is_progress and normalized["event_type"] == "tool_started":
            _precheck_task_progress(event.get('args'))
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
            if payload.get('tool_name') in CYCLE_CONTROL_TOOLS:
                self.cycle_calls.add(call)
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
        # A committed cycle assessment emits settlement before its own tool
        # return. That control receipt cannot block the accepted next objective;
        # all execution tools still must finish, and every call keeps its owner.
        if (state.get("completion_requested") and state["status"] == "running"
            and not any(self.calls[call][0] == identity
                        and not (state.get('cycle_settled') and call in self.cycle_calls)
                        for call in self.pending)):
            state["status"] = state.get("completion_status", "completed")
            state["duration_ms"] = max(0, round((self.clock() - cast(float, state["start"])) * 1000))
            if self.active == identity:
                self.active = None

    def cycle_progress(self, progress: Mapping[str, object], *, take_over: bool = False) -> dict[str, object]:
        """Apply host-confirmed cycle transitions, never model tool arguments."""
        identity, phase, text = progress.get('step_id'), progress.get('phase'), progress.get('text')
        if not isinstance(identity, str) or not identity or not isinstance(text, str) or not text:
            return {'task_step_error': 'Invalid committed research step.'}
        superseded = []
        if take_over and phase in {'started', 'updated'} and self.active is not None:
            if identity != self.active and identity not in self.steps:
                prior = self.steps[self.active]
                prior.update(status='limited', completion_status='limited',
                    finish_reason='此前叙述步骤尚未获完成确认，已由保存的研究步骤接管；在飞工具仍归属原步骤。',
                    duration_ms=max(0, round((self.clock() - cast(float, prior['start'])) * 1000)))
                superseded.append(self._public(self.active))
                # Keep calls and pending intact: late tool results still belong
                # to the superseded step, never the newly accepted objective.
                self.active = None
            elif identity == self.active:
                self.steps[identity]['title'] = text
        existing = self.steps.get(identity)
        if existing is not None:
            for key in ('questions', 'expected_outputs', 'derived_from', 'result_summary', 'next_action_reason'):
                if key in progress:
                    value = progress[key]
                    existing[key] = list(value) if isinstance(value, list) else value
        if existing and existing.get('cycle_settled') and phase == 'settled':
            expected = 'completed' if progress.get('outcome') == 'met' else progress.get('outcome')
            if expected == existing.get('completion_status'):
                return {'task_step': self._public(identity)}
        if existing and existing['status'] != 'running':
            expected = 'completed' if progress.get('outcome') == 'met' else progress.get('outcome')
            if phase == 'started' or (phase == 'settled' and expected == existing['status']):
                return {'task_step': self._public(identity)}
        if phase in {'started', 'updated'} and identity not in self.steps and self.active is None:
            self.steps[identity] = {'id': identity, 'number': len(self.steps) + 1,
                'title': text, 'status': 'running', 'start': self.clock(), 'tools': 0}
            for key in ('questions', 'expected_outputs', 'derived_from', 'result_summary', 'next_action_reason'):
                if key in progress:
                    value = progress[key]
                    self.steps[identity][key] = list(value) if isinstance(value, list) else value
            self.active = identity
        elif phase == 'settled' and identity == self.active:
            outcome = progress.get('outcome')
            if outcome not in {'met', 'partial', 'failed', 'limited'}:
                return {'task_step_error': 'Invalid committed research outcome.'}
            self.steps[identity].update(completion_requested=True, cycle_settled=True,
                completion_status='completed' if outcome == 'met' else outcome)
            self._finish_if_ready(identity)
        elif phase not in {'updated', 'started'} or identity != self.active:
            if phase in {'started', 'updated'} and self.active is not None:
                reason = ('the current step still has unfinished tool calls' if self.steps[self.active].get('cycle_settled')
                          else 'before the current step has a committed settlement')
                return {'task_step_error': 'Cannot start the research step: ' + reason + '; the existing step was retained.'}
            return {'task_step_error': 'Cannot apply the research transition: its phase or step does not match the active step; the existing step was retained.'}
        return {'task_step': self._public(identity), **({'task_steps': superseded} if superseded else {})}

    def _public(self, identity: str) -> dict[str, object]:
        return {key: value for key, value in self.steps[identity].items()
            if key in {"id", "number", "title", "status", "duration_ms", "response_ms", "first_text_ms", "usage", "finish_reason", "after_failed_steps",
                       "questions", "expected_outputs", "derived_from", "result_summary", "next_action_reason"}}


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
                self.steps[identity] = {"id": identity, "number": number, "title": "模型响应",
                    "status": "running", "start": self.clock(), "tools": 0}
                if self.pending_failed_steps:
                    self.steps[identity]["after_failed_steps"] = sorted(self.pending_failed_steps)
                    self.pending_failed_steps.clear()
                self.active = identity
            identity = self.active
            if identity is not None:
                state = self.steps[identity]
                if phase == "response_completed":
                    if event.get('response_kind') == 'error':
                        state['title'] = '模型响应失败'
                        state['finish_reason'] = 'error'
                        self.pending_failed_steps.add(identity)
                    elif not state.get("purpose"):
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
                    if state.get('finish_reason') != 'error':
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
                    _precheck_task_progress(event.get('args'))
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


class NativeStepTracker:
    """Adapt bounded native receipts to the same tracker used by professional sessions."""

    def __init__(self, *, prefix: str, objective_steps: bool = False):
        self.tracker = TaskStepTracker() if objective_steps else RuntimeStepTracker()
        self.prefix = prefix
        self.cycle_controlled = False
        self.cycle_step_ids: dict[str, str] = {}
        self.cycle_action_steps: dict[str, str] = {}
        self.graph_controlled = False

    def annotate(self, event: Mapping[str, object]) -> dict[str, object]:
        if event.get('type') == 'enterprise_graph_progress':
            self.graph_controlled = True
        if self.graph_controlled:
            # Graph nodes may execute at the same time. Their committed action
            # leases own tools; the legacy single-active-step fallback cannot
            # assign an unbound event to whichever node happened to run last.
            return {**event, 'runtime_step_tracking': True}
        if event.get('type') in {'delegation_child_started', 'delegation_child_tool', 'delegation_child_finished', 'delegation_child_response'}:
            action = event.get('parent_action_id')
            step = self.cycle_action_steps.get(action) if isinstance(action, str) else None
            if step is None:
                raise ValueError('research branch parent action has no accepted task step')
            # The host has checked the raw objective ID against the committed
            # checkpoint. Public consumers need the actual tracked identity,
            # which can differ when a narrative step used the same ID.
            return {**event, 'parent_step_id': self.prefix + '.' + step}
        internal = dict(event)
        kind = event.get('type')
        if kind == 'assistant_delta':
            internal['type'] = 'assistant_process_delta'
        if kind in {'tool_execution_start', 'tool_execution_end'}:
            internal.update(toolName=event.get('tool_name'), toolCallId=event.get('tool_call_id'))
            if type(event.get('is_error')) is bool:
                internal['ok'] = not event['is_error']
            if (event.get('tool_name') == 'agent_task_progress' and internal.get('ok') is True
                    and isinstance(event.get('task_progress'), Mapping)):
                _precheck_task_progress(event.get('task_progress'))
                record = TaskProgress.model_validate(event.get('task_progress')).model_dump(mode='json', exclude_none=True)
                internal.update(event='tool_result', capability='agent_task_progress', result=record)
        if kind == 'enterprise_cycle_progress' and isinstance(event.get('progress'), Mapping):
            progress = dict(cast(Mapping[str, object], event['progress']))
            identity = progress.get('step_id')
            if isinstance(identity, str):
                if identity not in self.cycle_step_ids:
                    alias, suffix = identity, 0
                    while alias in self.tracker.steps or alias in self.cycle_step_ids.values():
                        alias = 'cycle-' + sha256(f'{identity}:{suffix}'.encode()).hexdigest()[:32]
                        suffix += 1
                    self.cycle_step_ids[identity] = alias
                progress['step_id'] = self.cycle_step_ids[identity]
            tracked = self.tracker.cycle_progress(progress,
                                                 take_over=not self.cycle_controlled)
            if 'task_step_error' not in tracked:
                self.cycle_controlled = True
                action = event.get('action_id')
                step = tracked.get('task_step')
                if isinstance(action, str) and isinstance(step, dict) and isinstance(step.get('id'), str):
                    step_id = step['id']
                    previous = self.cycle_action_steps.get(action)
                    if previous is not None and previous != step_id:
                        raise ValueError('research cycle action changed its accepted task step')
                    self.cycle_action_steps[action] = step_id
        elif self.cycle_controlled and event.get('tool_name') == 'agent_task_progress':
            # Narrative progress remains visible, but cannot replace the
            # lifecycle admitted by the research checkpoint.
            tracked = {}
        else:
            tracked = self.tracker.annotate(internal)
        output = dict(event)
        for key in ('task_step', 'task_steps', 'task_step_id', 'task_step_number', 'step_tool_number', 'task_step_error', 'runtime_step_tracking'):
            if key in tracked:
                output[key] = tracked[key]
        raw_step = output.get('task_step')
        if isinstance(raw_step, dict):
            step = dict(raw_step)
            step['id'] = self.prefix + '.' + cast(str, step['id'])
            failed_steps = step.get('after_failed_steps')
            if isinstance(failed_steps, list):
                step['after_failed_steps'] = [self.prefix + '.' + item for item in failed_steps if isinstance(item, str)]
            output['task_step'] = step
        step_id = output.get('task_step_id')
        if isinstance(step_id, str):
            output['task_step_id'] = self.prefix + '.' + step_id
        raw_steps = output.get('task_steps')
        if isinstance(raw_steps, list):
            output['task_steps'] = [{**step, 'id': self.prefix + '.' + step['id']}
                                    for step in raw_steps if isinstance(step, dict) and isinstance(step.get('id'), str)]
        return output
