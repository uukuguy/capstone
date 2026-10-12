"""Host-bound research updates over the existing durable context ledger."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pydantic import ValidationError

from capability_agent.application.context_models import ContextEvent, ContextEventDraft
from capability_agent.application.context_store import ApplicationContextStore, ContextStoreError
from capability_agent.application.research_models import ResearchReceipt, ResearchState, ResearchUpdate


class ResearchController:
    """The host binds identities and reference admission, never the model."""

    def __init__(self, store: ApplicationContextStore, *, research_id: str, turn_id: str,
                 admit_reference: Callable[[str], bool]) -> None:
        self.store = store
        self.research_id = research_id
        self.turn_id = turn_id
        self.admit_reference = admit_reference

    def read(self) -> ResearchState | None:
        state = self.store.snapshot.core.research
        if state is not None and state.research_id != self.research_id:
            raise ContextStoreError("research identity does not match current state")
        return state

    def update(self, request: Mapping[str, Any]) -> ResearchReceipt:
        update, draft = self._draft(request)
        for ref in update.changes.references():
            if not self.admit_reference(ref):
                raise ContextStoreError("research reference is not admitted")
        return self._receipt(self.store.append_research_update(draft))

    def lookup_receipt(self, request: Mapping[str, Any]) -> ResearchReceipt | None:
        """Read a prior commit even after its turn ends; never create one."""
        _, draft = self._draft(request)
        event = self.store.find_research_update(draft)
        return self._receipt(event) if event is not None else None

    def _draft(self, request: Mapping[str, Any]) -> tuple[ResearchUpdate, ContextEventDraft]:
        try:
            update = ResearchUpdate.model_validate(request)
        except (TypeError, ValueError, ValidationError):
            raise ContextStoreError("invalid research update") from None
        return update, ContextEventDraft(
            event_type="research.updated", turn_id=self.turn_id,
            payload={"research_id": self.research_id, **update.model_dump(mode="json", exclude_unset=True)},
        )

    def _receipt(self, event: ContextEvent) -> ResearchReceipt:
        return ResearchReceipt(
            research_id=self.research_id, request_id=event.payload["request_id"],
            research_revision=event.payload["expected_revision"] + 1, event_sequence=event.sequence,
        )
