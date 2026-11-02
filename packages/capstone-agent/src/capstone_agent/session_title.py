"""Application-owned title state, independent of goals and execution revisions.

The caller selects admitted naming sources. This module neither ranks business
artifacts nor authorizes automatic execution. Store transitions atomically in
the session ledger; the revision check alone is not a database transaction.
"""
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone


@dataclass(frozen=True)
class SessionTitle:
    text: str
    source: str = 'default'
    revision: int = 0
    source_ref: str | None = None

    @classmethod
    def default(cls, name: str):
        # Persist once. Clients can show this UTC instant in their local zone.
        stamp = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
        return cls(f'{name} · {stamp}')

    def __post_init__(self):
        if (not isinstance(self.text, str) or not self.text.strip()
                or self.text != self.text.strip() or len(self.text) > 160
                or any(ord(char) < 32 for char in self.text)):
            raise ValueError('invalid session title')
        if not isinstance(self.source, str) or self.source not in {'default', 'automatic', 'user'}:
            raise ValueError('invalid title source')
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError('invalid title revision')
        if self.source_ref is not None and (
                not isinstance(self.source_ref, str) or not self.source_ref.strip()
                or len(self.source_ref) > 512):
            raise ValueError('invalid title source reference')
        if (self.source == 'automatic') != (self.source_ref is not None):
            raise ValueError('title source reference mismatch')

    def rename(self, text: str, *, expected_revision: int):
        if type(expected_revision) is not int or expected_revision != self.revision:
            raise ValueError('title revision conflict')
        return replace(self, text=text.strip() if isinstance(text, str) else text,
                       source='user', revision=self.revision + 1, source_ref=None)

    def suggest(self, text: str, *, expected_revision: int, source_ref: str):
        # An obsolete asynchronous suggestion is harmless, not a task failure.
        if (self.source == 'user' or type(expected_revision) is not int
                or expected_revision != self.revision):
            return self
        candidate = replace(self, text=text.strip() if isinstance(text, str) else text,
                            source='automatic', revision=self.revision + 1,
                            source_ref=source_ref)
        return self if candidate.text == self.text else candidate

    def to_document(self):
        return asdict(self)

    @classmethod
    def from_document(cls, value):
        if not isinstance(value, dict) or set(value) != {'text', 'source', 'revision', 'source_ref'}:
            raise ValueError('invalid title document')
        return cls(**value)


def rename_session(snapshot, command, *, archived):
    """Validate a user rename without changing Work or execution state."""
    if archived:
        return None, 'thread_archived'
    if command.get('run_id') is not None and command['run_id'] != snapshot.run.run_id:
        return None, 'run_mismatch'
    if command['target']['id'] != snapshot.thread_id:
        return None, 'title_target_mismatch'
    if set(command['payload']) != {'text'}:
        return None, 'invalid_session_title'
    current = snapshot.session_title
    revision = 0 if current is None else current.revision
    if command['target']['expected_revision'] != revision:
        return None, 'title_revision_conflict'
    try:
        # No inferred type/name is persisted for legacy sessions.
        value = command['payload']['text']
        return SessionTitle(value.strip() if isinstance(value, str) else value,
                            'user', revision + 1), None
    except ValueError:
        return None, 'invalid_session_title'
