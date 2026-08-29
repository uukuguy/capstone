from __future__ import annotations

from collections.abc import Iterator, Mapping

import pytest
from pydantic import ValidationError

from capability_agent.application.context_models import (
    ApplicationContext,
    ContextEventDraft,
    CoreContext,
    DomainStateEnvelope,
)
from capability_agent.application.context_reducer import (
    ContextTransitionError,
    canonical_state_hash,
    reduce_context,
)


@pytest.fixture
def initial_context() -> ApplicationContext:
    return ApplicationContext.initial(
        run_id="run-1",
        domains={
            "grid": "pandapower-analysis-state/1.0",
            "inventory": "inventory-state/1.0",
        },
    )


def test_domain_delta_can_update_only_its_binding(
    initial_context: ApplicationContext,
) -> None:
    changed = reduce_context(
        initial_context,
        ContextEventDraft(
            event_type="domain.state.projected",
            binding_id="grid",
            payload={
                "schema_id": "pandapower-analysis-state/1.0",
                "previous_revision": 0,
                "state": {
                    "active_context_ref": "context:sha256:" + "a" * 64,
                },
            },
        ),
    )

    assert changed.domains["grid"].revision == 1
    assert changed.domains["inventory"].revision == 0
    assert changed.revision == initial_context.revision + 1
    assert changed.state_hash == canonical_state_hash(changed)


def test_domain_delta_rejects_unknown_binding_schema_drift_and_stale_revision(
    initial_context: ApplicationContext,
) -> None:
    cases = (
        ("unknown binding", "missing", "inventory-state/1.0", 0),
        ("schema drift", "grid", "other-state/2.0", 0),
        ("stale revision", "grid", "pandapower-analysis-state/1.0", 1),
    )

    for label, binding_id, schema_id, previous_revision in cases:
        with pytest.raises(ContextTransitionError, match=label):
            reduce_context(
                initial_context,
                ContextEventDraft(
                    event_type="domain.state.projected",
                    binding_id=binding_id,
                    payload={
                        "schema_id": schema_id,
                        "previous_revision": previous_revision,
                        "state": {},
                    },
                ),
            )


def test_domain_delta_rejects_foreign_reference_ownership(
    initial_context: ApplicationContext,
) -> None:
    with pytest.raises(ContextTransitionError, match="foreign reference"):
        reduce_context(
            initial_context,
            ContextEventDraft(
                event_type="domain.state.projected",
                binding_id="grid",
                payload={
                    "schema_id": "pandapower-analysis-state/1.0",
                    "previous_revision": 0,
                    "state": {
                        "result_ref": {
                            "binding_id": "inventory",
                            "ref": "result:sha256:" + "a" * 64,
                        },
                    },
                },
            ),
        )


def test_domain_delta_rejects_sibling_binding_fields(
    initial_context: ApplicationContext,
) -> None:
    with pytest.raises(ContextTransitionError, match="sibling binding"):
        reduce_context(
            initial_context,
            ContextEventDraft(
                event_type="domain.state.projected",
                binding_id="grid",
                payload={
                    "schema_id": "pandapower-analysis-state/1.0",
                    "previous_revision": 0,
                    "state": {"inventory": {"status": "visible"}},
                },
            ),
        )


def test_domain_delta_rejects_foreign_binding_ids_in_owner_lists(
    initial_context: ApplicationContext,
) -> None:
    with pytest.raises(ContextTransitionError, match="foreign reference"):
        reduce_context(
            initial_context,
            ContextEventDraft(
                event_type="domain.state.projected",
                binding_id="grid",
                payload={
                    "schema_id": "pandapower-analysis-state/1.0",
                    "previous_revision": 0,
                    "state": {
                        "owner_binding_ids": ["grid", "inventory"],
                    },
                },
            ),
        )


@pytest.mark.parametrize("owner_value", [None, {}, [], ["grid"], ("grid",)])
def test_domain_delta_requires_scalar_ownership_fields_to_be_exact_binding_strings(
    initial_context: ApplicationContext,
    owner_value: object,
) -> None:
    with pytest.raises(ContextTransitionError, match="foreign reference"):
        reduce_context(
            initial_context,
            ContextEventDraft(
                event_type="domain.state.projected",
                binding_id="grid",
                payload={
                    "schema_id": "pandapower-analysis-state/1.0",
                    "previous_revision": 0,
                    "state": {"owner_binding_id": owner_value},
                },
            ),
        )


@pytest.mark.parametrize(
    "owner_value",
    [None, {}, "grid", ["grid", "inventory"], ["grid", 1]],
)
def test_domain_delta_requires_ownership_lists_of_current_binding_strings(
    initial_context: ApplicationContext,
    owner_value: object,
) -> None:
    with pytest.raises(ContextTransitionError, match="foreign reference"):
        reduce_context(
            initial_context,
            ContextEventDraft(
                event_type="domain.state.projected",
                binding_id="grid",
                payload={
                    "schema_id": "pandapower-analysis-state/1.0",
                    "previous_revision": 0,
                    "state": {"owner_binding_ids": owner_value},
                },
            ),
        )


@pytest.mark.parametrize("owner_value", [["grid"], ("grid",)])
def test_domain_delta_accepts_current_binding_ownership_lists(
    initial_context: ApplicationContext,
    owner_value: object,
) -> None:
    changed = reduce_context(
        initial_context,
        ContextEventDraft(
            event_type="domain.state.projected",
            binding_id="grid",
            payload={
                "schema_id": "pandapower-analysis-state/1.0",
                "previous_revision": 0,
                "state": {"owner_binding_ids": owner_value},
            },
        ),
    )

    assert changed.domains["grid"].revision == 1


class _HostileMapping(Mapping[str, object]):
    def __iter__(self) -> Iterator[str]:
        raise OSError("secret=/private/path")

    def __len__(self) -> int:
        return 1

    def __getitem__(self, key: str) -> object:
        del key
        raise OSError("secret=/private/path")

    def items(self):
        raise OSError("secret=/private/path")

    def __repr__(self) -> str:
        return "<hostile secret=/private/path>"


@pytest.mark.parametrize(
    "builder",
    [
        lambda value: ContextEventDraft(
            event_type="diagnostic.recorded", payload=value
        ),
        lambda value: CoreContext(input=value),
        lambda value: DomainStateEnvelope(schema_id="domain-state/1.0", state=value),
    ],
)
def test_public_mapping_models_sanitize_hostile_mapping_errors(builder) -> None:
    with pytest.raises(ValidationError) as error:
        builder(_HostileMapping())

    message = str(error.value)
    assert "secret" not in message
    assert "/private/path" not in message


def test_reducer_uses_a_closed_event_allowlist_and_terminal_context_is_immutable(
    initial_context: ApplicationContext,
) -> None:
    with pytest.raises(ValidationError):
        ContextEventDraft(event_type="arbitrary.event", payload={})  # type: ignore[arg-type]

    running = reduce_context(
        initial_context,
        ContextEventDraft(event_type="analysis.started", payload={}),
    )
    completed = reduce_context(
        running,
        ContextEventDraft(event_type="analysis.completed", payload={}),
    )
    with pytest.raises(ContextTransitionError, match="terminal"):
        reduce_context(
            completed,
            ContextEventDraft(
                event_type="diagnostic.recorded",
                payload={"message": "late"},
            ),
        )


def test_context_and_event_payload_are_deeply_immutable(
    initial_context: ApplicationContext,
) -> None:
    draft = ContextEventDraft(
        event_type="diagnostic.recorded",
        payload={"details": {"items": ["one"]}},
    )
    with pytest.raises(TypeError):
        draft.payload["details"] = {}  # type: ignore[index]
    with pytest.raises(TypeError):
        draft.payload["details"]["items"][0] = "two"  # type: ignore[index]

    changed = reduce_context(initial_context, draft)
    with pytest.raises(TypeError):
        changed.core.diagnostics[0]["details"]["items"] = ()  # type: ignore[index]


@pytest.mark.parametrize(
    "invalid_value",
    [float("nan"), float("inf"), {"not", "json"}, b"bytes"],
)
def test_context_payload_rejects_non_json_values(invalid_value: object) -> None:
    with pytest.raises((ValidationError, TypeError)):
        ContextEventDraft(
            event_type="diagnostic.recorded",
            payload={"value": invalid_value},
        )


def test_single_character_ids_are_portable() -> None:
    context = ApplicationContext.initial(
        run_id="a",
        domains={"b": "domain-state/1.0"},
    )

    assert context.run_id == "a"
    assert tuple(context.domains) == ("b",)
