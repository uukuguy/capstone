"""Host-bound research updates over the existing durable context ledger."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pydantic import ValidationError

from capability_agent.application.context_models import ContextEvent, ContextEventDraft
from capability_agent.application.context_store import ApplicationContextStore, ContextStoreError
from capability_agent.application.research_models import ResearchReceipt, ResearchState, ResearchUpdate
from capability_agent.runtime.capacity import runtime_limits as resolve_limits
from capability_agent.application.research_models import _check_research_capacity
from capability_agent.application.context_reducer import reduce_context, ContextTransitionError


class ResearchController:
    """The host binds identities and reference admission, never the model."""

    def __init__(self, store: ApplicationContextStore, *, research_id: str, turn_id: str,
                 admit_reference: Callable[[str], bool], runtime_limits=None) -> None:
        self.store = store
        self.research_id = research_id
        self.turn_id = turn_id
        self.admit_reference = admit_reference
        self.runtime_limits = resolve_limits(runtime_limits)

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
        try:
            candidate = reduce_context(self.store.snapshot, draft)
        except ContextTransitionError:
            candidate = None  # The store owns CAS/retry/transition diagnostics.
        if candidate is not None and candidate.core.research is not None:
            _check_research_capacity(candidate.core.research.model_dump(), self.runtime_limits)
        return self._receipt(self.store.append_research_update(draft))

    def lookup_receipt(self, request: Mapping[str, Any]) -> ResearchReceipt | None:
        """Read a prior commit even after its turn ends; never create one."""
        _, draft = self._draft(request)
        event = self.store.find_research_update(draft)
        return self._receipt(event) if event is not None else None

    def preview(self, request: Mapping[str, Any]) -> ResearchState:
        """Project with the existing reducer before a bounded response commits."""
        _, draft = self._draft(request)
        state=reduce_context(self.store.snapshot,draft).core.research
        assert state is not None
        return state

    def _draft(self, request: Mapping[str, Any]) -> tuple[ResearchUpdate, ContextEventDraft]:
        if isinstance(request,Mapping):
            _check_research_capacity(request.get('changes',{}),self.runtime_limits)
        try:
            update = ResearchUpdate.model_validate(request, context={'runtime_limits': self.runtime_limits})
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
