"""Immutable reader text from one Thread; historical text is not evidence."""

from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Mapping, Sequence

MAX_HISTORY_TURNS = 16
MAX_HISTORY_BYTES = 32 * 1024
MAX_MESSAGE_BYTES = 2048
_FIELDS = {"message_id", "role", "content", "turn_id", "attempt_id", "model_context_id", "status"}
_TERMINAL = {"completed", "failed", "cancelled", "interrupted"}
_OBJECT_FIELDS = {"object_id", "model_id", "model_revision", "implementation_family"}


@dataclass(frozen=True, slots=True)
class ConversationContext:
    history_cutoff: int = 0
    messages: tuple[Mapping[str, str], ...] = ()
    truncated: bool = False
    objects: tuple[Mapping[str, str], ...] = ()

    def __post_init__(self) -> None:
        if type(self.history_cutoff) is not int or self.history_cutoff < 0 or type(self.truncated) is not bool:
            raise ValueError("conversation context metadata is invalid")
        copies = []
        for message in self.messages:
            if (not isinstance(message, Mapping) or set(message) != _FIELDS
                    or any(not isinstance(value, str) for value in message.values())
                    or message["role"] not in {"user", "assistant"}
                    or message["status"] not in _TERMINAL
                    or (message["role"] == "assistant" and message["status"] != "completed")):
                raise ValueError("conversation context message is invalid")
            copies.append(MappingProxyType(dict(message)))
        if len(copies) > MAX_HISTORY_TURNS * 2 or sum(len(m["content"].encode()) for m in copies) > MAX_HISTORY_BYTES:
            raise ValueError("conversation context exceeds bounds")
        object.__setattr__(self, "messages", tuple(copies))
        objects = []
        seen = set()
        contexts = {message["model_context_id"] for message in copies}
        for item in self.objects:
            if (not isinstance(item, Mapping) or set(item) != _OBJECT_FIELDS
                    or any(not isinstance(value, str) or not value or len(value) > 256 for value in item.values())
                    or item["object_id"] not in contexts or item["object_id"] in seen):
                raise ValueError("conversation context object is invalid")
            seen.add(item["object_id"])
            objects.append(MappingProxyType(dict(item)))
        if len(objects) > MAX_HISTORY_TURNS:
            raise ValueError("conversation context objects exceed bounds")
        object.__setattr__(self, "objects", tuple(objects))

    def to_document(self) -> dict[str, object]:
        return {"history_cutoff": self.history_cutoff, "messages": [dict(m) for m in self.messages],
                "truncated": self.truncated, "objects": [dict(item) for item in self.objects]}

    @classmethod
    def from_document(cls, document: Mapping[str, object]) -> "ConversationContext":
        required = {"history_cutoff", "messages", "truncated"}
        if (not required <= document.keys() or document.keys() - required - {"objects"}
                or not isinstance(document["messages"], (list, tuple))):
            raise ValueError("conversation context document is invalid")
        cutoff, truncated = document['history_cutoff'], document['truncated']
        if type(cutoff) is not int or type(truncated) is not bool:
            raise ValueError('conversation context metadata is invalid')
        objects = document.get("objects", [])
        if not isinstance(objects, (list, tuple)):
            raise ValueError("conversation context objects are invalid")
        return cls(cutoff, tuple(document["messages"]), truncated, tuple(objects))


def project_conversation(rows: Sequence[Mapping[str, object]], cutoff: int, *, truncated: bool = False) -> ConversationContext:
    """Project ordered terminal records supplied by either ledger adapter."""
    groups = []
    truncated = truncated or len(rows) > MAX_HISTORY_TURNS
    for row in rows[-MAX_HISTORY_TURNS:]:
        status = row["status"]
        group = []
        for role, text in (("user", row["instruction"]), ("assistant", row.get("answer"))):
            if role == "assistant" and (status != "completed" or not isinstance(text, str) or not text):
                continue
            if not isinstance(text, str):
                continue
            encoded = text.encode()
            if len(encoded) > MAX_MESSAGE_BYTES:
                text = encoded[:MAX_MESSAGE_BYTES].decode("utf-8", errors="ignore")
                truncated = True
            group.append({"message_id": str(row["attempt_id"]) + ":" + role, "role": role, "content": text,
                          "turn_id": row["turn_id"], "attempt_id": row["attempt_id"],
                          "model_context_id": row["model_context_id"], "status": status})
        groups.append(group)
    total = sum(len(m["content"].encode()) for group in groups for m in group)
    while groups and total > MAX_HISTORY_BYTES:
        total -= sum(len(m["content"].encode()) for m in groups.pop(0))
        truncated = True
    messages = tuple(m for group in groups for m in group)
    included = {message["model_context_id"] for message in messages}
    objects = {}
    for row in rows[-MAX_HISTORY_TURNS:]:
        item = row.get("object")
        if isinstance(item, Mapping) and item.get("object_id") in included:
            objects[item["object_id"]] = item
    return ConversationContext(cutoff, messages, truncated, tuple(objects.values()))
