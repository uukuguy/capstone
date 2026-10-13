"""Application-owned stage boundaries. Execution completion is not verification."""
from collections.abc import Callable, Mapping
import time
from typing import cast
from datetime import datetime, timezone


def preparation_seconds(started_at: str | None) -> float:
    if started_at is None:
        return 0
    try:
        return max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(started_at)).total_seconds())
    except (ValueError, TypeError):
        return 0


def preparation_step() -> dict[str, object]:
    return {'id': 'task-preparation', 'number': 1, 'title': '任务准备', 'status': 'running'}


class ExecutionStages:
    def __init__(self, *, preparation_seconds: float = 0, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self.steps = {'task-preparation': {**preparation_step(), 'start': clock() - max(0, preparation_seconds)}}
        self.active = 'task-preparation'
        self.execution_entry: float | None = None

    def mark_execution_entry(self) -> None:
        self.execution_entry = self.clock()

    def _public(self, identity: str) -> dict[str, object]:
        return {key: value for key, value in self.steps[identity].items() if key != 'start'}

    def _close(self, at: float | None = None) -> dict[str, object]:
        state = self.steps[self.active]
        state['status'] = 'completed'
        state['duration_ms'] = max(0, round(((self.clock() if at is None else at) - cast(float, state['start'])) * 1000))
        return self._public(self.active)

    def _open_unframed_execution(self) -> dict[str, object] | None:
        if self.active != 'task-preparation' or self.execution_entry is None:
            return None
        previous = self._close(self.execution_entry)
        self.active = 'task-execution'
        self.steps[self.active] = {'id': self.active, 'number': len(self.steps) + 1,
            'title': '执行任务', 'status': 'running', 'start': self.execution_entry}
        return previous

    def annotate(self, event: Mapping[str, object]) -> dict[str, object]:
        output = dict(event)
        original = event.get('payload')
        if not isinstance(original, Mapping):
            return output
        payload = dict(original)
        if event.get('event_type') in {'tool_started', 'tool_completed'} and 'task_step' not in payload:
            previous = self._open_unframed_execution()
            if previous is not None:
                payload['task_steps'] = [previous]
            if self.active == 'task-execution':
                payload['task_step'] = self._public(self.active)
                payload['task_step_id'] = self.active
                payload['task_step_number'] = self.steps[self.active]['number']
        step = payload.get('task_step')
        if isinstance(step, Mapping) and isinstance(step.get('id'), str):
            identity = step['id']
            if identity not in self.steps:
                previous = self._close()
                self.steps[identity] = {'id': identity, 'number': len(self.steps) + 1,
                    'title': step.get('title', '执行任务'), 'status': 'running', 'start': self.clock()}
                self.active = identity
                payload['task_steps'] = [previous]
            state = self.steps[identity]
            for key in ('title', 'response_ms', 'finish_reason'):
                if key in step:
                    state[key] = step[key]
            if step.get('status') == 'completed' and identity == self.active:
                self._close()
            payload['task_step'] = self._public(identity)
        parent = payload.get('task_step_id')
        if isinstance(parent, str) and parent in self.steps and 'task_step_number' in payload:
            payload['task_step_number'] = self.steps[parent]['number']
        output['payload'] = payload
        return output

    def begin_finalization(self) -> dict[str, object] | None:
        if self.active.startswith('task-finalization-'):
            return None
        preparation = self._open_unframed_execution()
        previous = self._close()
        number = len(self.steps) + 1
        identity = f'task-finalization-{number}'
        self.steps[identity] = {'id': identity, 'number': number, 'title': '核验与结果整理',
            'status': 'running', 'start': self.clock()}
        self.active = identity
        return {'event_type': 'runtime_action', 'runtime_mode': 'capstone', 'visibility': 'public',
            'payload': {'phase': 'started', 'task_steps': ([preparation] if preparation is not None else []) + [previous], 'task_step': self._public(identity)}}

    def finish(self) -> list[dict[str, object]]:
        return [self._close()]
