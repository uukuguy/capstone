"""Application-neutral planning guidance, selected by execution adapters."""
from dataclasses import dataclass
from hashlib import sha256
from importlib.resources import files


@dataclass(frozen=True)
class TaskPlanningPolicy:
    version: str
    text: str

    @property
    def sha256(self) -> str:
        return sha256(self.text.encode()).hexdigest()


def task_planning_policy(version: str) -> TaskPlanningPolicy:
    resources = {'1.0.0': '1.0', '1.1.0': '1.1', '1.2.0': '1.2', '1.3.0': '1.3', '1.4.0': '1.4', '1.5.0': '1.5', '1.6.0': '1.6', '1.7.0': '1.7'}
    if version not in resources:
        raise ValueError('task planning policy version is not registered')
    return TaskPlanningPolicy(version, files(__package__).joinpath(
        f'resources/task-planning-policy-{resources[version]}.md').read_text(encoding='utf-8'))
