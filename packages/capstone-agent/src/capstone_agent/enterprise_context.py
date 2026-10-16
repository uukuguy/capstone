"""Application-owned work identities, independent of business model selection.

These immutable records are supplied by the host. They describe the selected
context; they do not grant tool access or replace live authorization checks.
"""

from dataclasses import dataclass
from collections.abc import Mapping
import re

from capability_agent.application.context_models import PORTABLE_ID_PATTERN
from .thread_protocol import ModelContextSnapshot


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")


def _identity(value: object, name: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"invalid {name}")


@dataclass(frozen=True, slots=True)
class WorkBinding:
    thread_id: str
    work_id: str
    research_id: str

    def __post_init__(self) -> None:
        _identity(self.thread_id, "work thread identity")
        _identity(self.work_id, "work identity")
        if not isinstance(self.research_id, str) or not PORTABLE_ID_PATTERN.fullmatch(self.research_id):
            raise ValueError("invalid research identity")

    def to_document(self) -> dict[str, object]:
        return {"thread_id": self.thread_id, "work_id": self.work_id, "research_id": self.research_id}

    @classmethod
    def from_document(cls, value: object) -> "WorkBinding":
        if not isinstance(value, Mapping) or set(value) != {"thread_id", "work_id", "research_id"}:
            raise ValueError("invalid work binding")
        # Validate before constructing so non-string wire values cannot be coerced.
        for name in ("thread_id", "work_id", "research_id"):
            if not isinstance(value[name], str):
                raise ValueError("invalid work binding identity")
        return cls(value["thread_id"], value["work_id"], value["research_id"])


@dataclass(frozen=True, slots=True)
class TaskContext:
    binding: WorkBinding
    goal_revision: int
    snapshot_id: str
    model_contexts: tuple[ModelContextSnapshot, ...] = ()
    resource_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.binding, WorkBinding):
            raise ValueError("invalid work binding")
        if type(self.goal_revision) is not int or self.goal_revision < 1:
            raise ValueError("invalid goal revision")
        _identity(self.snapshot_id, "task snapshot identity")
        if not isinstance(self.model_contexts, tuple) or any(
            not isinstance(model, ModelContextSnapshot) for model in self.model_contexts
        ):
            raise ValueError("invalid task model contexts")
        if len({model.id for model in self.model_contexts}) != len(self.model_contexts):
            raise ValueError("duplicate task model context")
        if not isinstance(self.resource_refs, tuple) or any(
            not isinstance(ref, str) or not ref.strip() for ref in self.resource_refs
        ) or len(set(self.resource_refs)) != len(self.resource_refs):
            raise ValueError("invalid task resource references")

    def to_document(self) -> dict[str, object]:
        return {"binding": self.binding.to_document(), "goal_revision": self.goal_revision,
                "snapshot_id": self.snapshot_id,
                "model_contexts": [model.to_document() for model in self.model_contexts],
                "resource_refs": list(self.resource_refs)}

    @classmethod
    def from_document(cls, value: object) -> "TaskContext":
        fields = {"binding", "goal_revision", "snapshot_id", "model_contexts", "resource_refs"}
        if not isinstance(value, Mapping) or set(value) != fields:
            raise ValueError("invalid task context")
        if (type(value["goal_revision"]) is not int or not isinstance(value["snapshot_id"], str)
                or not isinstance(value["model_contexts"], list)
                or not isinstance(value["resource_refs"], list)):
            raise ValueError("invalid task context fields")
        return cls(WorkBinding.from_document(value["binding"]), value["goal_revision"],
                   value["snapshot_id"],
                   tuple(ModelContextSnapshot.from_document(model) for model in value["model_contexts"]),
                   tuple(value["resource_refs"]))
