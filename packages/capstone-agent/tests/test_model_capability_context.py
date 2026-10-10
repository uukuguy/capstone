from __future__ import annotations

from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from capstone_agent.model_capability import CapstoneModelCapabilityCatalog, ModelCapabilityProfileInfo
from capstone_agent.model_capability_context import (
    ApplicationProfileCapabilityContribution,
    ApplicationProfileCapabilityHandle,
    ModelCapabilityContextOwner,
    register_application_profile,
)
from capstone_agent.thread_protocol import AttemptSnapshot, ModelContextSnapshot
from capstone_agent.thread_service import AttemptClaim
from capstone_model_capability_spi import ModelCapabilityDescriptor, ModelCapabilityRegistry
from capstone_agent.request_intent import IntentDecision, IntentRequest
from capstone_agent.turn_router import TurnPlan


class _Handle:
    def __init__(self, descriptor, log):
        self.descriptor = descriptor
        self.log = log

    def close(self):
        self.log.append("handle:" + self.descriptor.profile_id)


class _Contribution:
    def __init__(self, descriptor, model_context, log, *, fail_close=False):
        self.descriptor = descriptor
        self.model_context = model_context
        self.log = log
        self.fail_close = fail_close

    def close(self):
        self.log.append("contribution:" + self.descriptor.profile_id)
        if self.fail_close:
            raise RuntimeError("cleanup failed")


class _Adapter:
    def __init__(self, log, *, fail=False, drift=False, fail_close=False):
        self.log = log
        self.fail = fail
        self.drift = drift
        self.fail_close = fail_close
        self.inputs = []

    def prepare(self, handle, *, model_context):
        self.inputs.append((handle, model_context))
        if self.fail:
            raise RuntimeError("adapter failed")
        return _Contribution(
            handle.descriptor,
            replace(model_context, selection_revision="sel_wrong") if self.drift else model_context,
            self.log, fail_close=self.fail_close,
        )


def _claim(*, profiles=(("static", "1.0.0"),), thread_id="thr_1", run_id="run_1"):
    return AttemptClaim(
        thread_id=thread_id, run_id=run_id,
        attempt=AttemptSnapshot("turn_1", "attempt_1", "running", "ctx_1"),
        kind="send_ordinary", instruction="inspect", model_context_id="ctx_1",
        selection_revision="sel_1", lease_token="lease_1",
        model_context=ModelContextSnapshot(
            "ctx_1", "ieee39", "revision:sha256:" + "a" * 64,
            "pandapower", "sel_1", profiles,
        ),
    )


def _owner(log, *, second=None, first=None, seal=True, **limits):
    registry = ModelCapabilityRegistry()
    catalog = CapstoneModelCapabilityCatalog(registry)
    owner = ModelCapabilityContextOwner(catalog, **limits)
    adapters = {"static": first or _Adapter(log)}
    if second is not None:
        adapters["extra"] = second
    for profile_id, adapter in adapters.items():
        descriptor = ModelCapabilityDescriptor(profile_id, "1.0.0")
        catalog.register_profile(
            ModelCapabilityProfileInfo(descriptor, profile_id, ("pandapower",)),
            lambda descriptor=descriptor: _Handle(descriptor, log),
        )
        adapter.descriptor = descriptor
        owner.register_adapter(descriptor.reference, adapter)
    if seal:
        registry.seal()
        owner.seal()
    return owner, adapters


def _with_intent(claim, references, *, operation="business_execute", catalog_references=(), goal_documents=None):
    identities = list(dict.fromkeys([*references, *catalog_references]))
    enabled = {f"{profile_id}@{version}" for profile_id, version in claim.model_context.enabled_profiles}
    request = IntentRequest.from_document({
        "schema": "capstone-intent-request/1", "thread_id": claim.thread_id,
        "turn_id": claim.attempt.turn_id, "attempt_id": claim.attempt.attempt_id,
        "instruction": claim.instruction, "history_cutoff": 0, "messages": [], "objects": [],
        "capabilities": [{"capability_id": identity, "available": True, "enabled": identity in enabled}
                         for identity in identities], "mode_hint": None,
    })
    goals = [{"goal_id": "goal_1", "description": "Use selected resources", "operation": operation,
              "message_refs": [], "object_refs": [], "capability_refs": references,
              "missing_requirements": []}]
    if catalog_references:
        goals.append({"goal_id": "goal_2", "description": "Discuss catalog metadata", "operation": "catalog_lookup",
                      "message_refs": [], "object_refs": [], "capability_refs": list(catalog_references),
                      "missing_requirements": []})
    if goal_documents is not None:
        goals = goal_documents
    decision = IntentDecision.from_document({
        "schema": "capstone-intent-decision/1", "attempt_id": claim.attempt.attempt_id,
        "history_cutoff": 0, "relationship": "independent", "clarification": None,
        "goals": goals,
    }, request)
    plan = TurnPlan(claim.attempt.turn_id, claim.attempt.attempt_id,
                    "professional" if decision.requires_business else "ordinary", "fixture",
                    "plan_1", None, {}, intent_decision=decision)
    return replace(claim, turn_plan=plan)


def test_intent_subsets_have_distinct_cache_entries_and_release_pins():
    log = []
    owner, adapters = _owner(log, second=_Adapter(log))
    claim = _claim(profiles=(("static", "1.0.0"), ("extra", "1.0.0")))
    static_claim = _with_intent(claim, ["static@1.0.0"])
    extra_claim = _with_intent(claim, ["extra@1.0.0"])
    static = owner.acquire(static_claim)
    extra = owner.acquire(extra_claim)
    assert static is not extra
    assert static.selected_profiles == (("static", "1.0.0"),)
    assert extra.selected_profiles == (("extra", "1.0.0"),)
    assert static.model_context == extra.model_context == claim.model_context
    assert owner.acquire(static_claim) is static
    assert len(adapters["static"].inputs) == len(adapters["extra"].inputs) == 1
    owner.release(static)
    owner.release(extra)
    assert owner.resource_counts() == {"retained": 2, "active": 1}
    with pytest.raises(RuntimeError, match="active"):
        owner.close_run(claim.thread_id, claim.run_id)
    owner.release(static)
    assert owner.resource_counts() == {"retained": 2, "active": 0}
    owner.close_run(claim.thread_id, claim.run_id)
    assert sorted(log) == ["contribution:extra", "contribution:static", "handle:extra", "handle:static"]


@pytest.mark.parametrize("reference", ["extra@1.0.0", "unknown@1.0.0", "static@2.0.0", "static"])
def test_intent_cannot_enable_unselected_or_unknown_resources(reference):
    owner, adapters = _owner([], second=_Adapter([]))
    with pytest.raises(ValueError, match="enabled"):
        owner.prepare(_with_intent(_claim(), [reference]))
    assert all(not adapter.inputs for adapter in adapters.values())
    assert owner.resource_counts() == {"retained": 0, "active": 0}
    owner.close()


def test_intent_ordinary_empty_subset_preserves_model_selection():
    owner, adapters = _owner([])
    claim = _claim()
    ordinary = _with_intent(claim, [], operation="answer")
    context = owner.acquire(ordinary)
    assert context.handles == context.contributions == context.selected_profiles == ()
    assert context.model_context is claim.model_context
    assert ordinary.model_context.enabled_profiles == (("static", "1.0.0"),)
    assert ordinary.selection_revision == "sel_1"
    assert adapters["static"].inputs == []
    owner.release(context)
    owner.close()


def test_business_intent_needs_an_enabled_resource_reference():
    owner, adapters = _owner([])
    with pytest.raises(ValueError, match="business"):
        owner.prepare(_with_intent(_claim(), []))
    assert adapters["static"].inputs == []
    owner.close()


def test_changed_snapshot_cannot_hide_drift_under_a_different_subset():
    owner, adapters = _owner([], second=_Adapter([]))
    claim = _claim(profiles=(("static", "1.0.0"), ("extra", "1.0.0")))
    owner.prepare(_with_intent(claim, ["static@1.0.0"]))
    changed = replace(claim, model_context=replace(claim.model_context, model_revision="revision:sha256:" + "b" * 64))
    with pytest.raises(ValueError, match="snapshot"):
        owner.prepare(_with_intent(changed, ["extra@1.0.0"]))
    assert adapters["extra"].inputs == []
    owner.close()


@pytest.mark.parametrize("enabled_profiles", [(("static", "1.0.0"),), (("static", "1.0.0"), ("extra", "1.0.0"))])
def test_mixed_catalog_and_business_intent_prepares_only_business_resources(enabled_profiles):
    owner, adapters = _owner([], second=_Adapter([]))
    claim = _with_intent(_claim(profiles=enabled_profiles), ["static@1.0.0"], catalog_references=["extra@1.0.0"])
    context = owner.acquire(claim)
    assert context.selected_profiles == (("static", "1.0.0"),)
    assert adapters["extra"].inputs == []
    assert context.model_context is claim.model_context
    owner.release(context)
    owner.close()


@pytest.mark.parametrize("operation", ["catalog_lookup", "answer", "rewrite"])
def test_metadata_references_do_not_prepare_business_resources(operation):
    owner, adapters = _owner([], second=_Adapter([]))
    context = owner.acquire(_with_intent(_claim(), ["extra@1.0.0"], operation=operation))
    assert context.selected_profiles == context.handles == context.contributions == ()
    assert all(not adapter.inputs for adapter in adapters.values())
    owner.release(context)
    owner.close()


@pytest.mark.parametrize("dependencies,business_first,expected", [
    ([], False, (("static", "1.0.0"),)),
    (["weather"], False, ()),
    (None, False, ()),
    ([], True, (("static", "1.0.0"),)),
])
def test_missing_weather_only_blocks_dependent_business_resources(dependencies, business_first, expected):
    weather = {"goal_id": "weather", "description": "Get weather", "operation": "external_lookup",
               "message_refs": [], "object_refs": [], "capability_refs": [],
               "missing_requirements": ["Weather service is unavailable"], "depends_on": []}
    business = {"goal_id": "business", "description": "Analyze the selected model", "operation": "business_execute",
                "message_refs": [], "object_refs": [], "capability_refs": ["static@1.0.0"],
                "missing_requirements": []}
    if dependencies is not None:
        business["depends_on"] = dependencies
    goals = [business, weather] if business_first else [weather, business]
    claim = _with_intent(_claim(), ["static@1.0.0"], goal_documents=goals)
    owner, adapters = _owner([])
    context = owner.acquire(claim)
    assert context.selected_profiles == expected
    assert len(adapters["static"].inputs) == len(expected)
    assert context.model_context is claim.model_context
    owner.release(context)
    owner.close()


def test_health_counts_do_not_wait_for_slow_model_preparation():
    entered, release = Event(), Event()

    class SlowAdapter(_Adapter):
        def prepare(self, handle, *, model_context):
            entered.set()
            assert release.wait(5)
            return super().prepare(handle, model_context=model_context)

    owner, _ = _owner([], first=SlowAdapter([]))
    with ThreadPoolExecutor(max_workers=2) as pool:
        preparing = pool.submit(owner.acquire, _claim())
        assert entered.wait(1)
        try:
            assert pool.submit(owner.resource_counts).result(timeout=.5) == {'retained': 0, 'active': 0}
        finally:
            release.set()
        context = preparing.result(timeout=2)
    assert owner.resource_counts() == {'retained': 1, 'active': 1}
    owner.release(context)
    assert owner.resource_counts() == {'retained': 1, 'active': 0}
    owner.close()
    assert owner.resource_counts() == {'retained': 0, 'active': 0}


def test_prepares_exact_snapshot_and_reuses_run_context_across_attempts():
    log = []
    owner, adapters = _owner(log)
    claim = _claim()
    context = owner.prepare(claim)
    retry = replace(claim, attempt=replace(claim.attempt, attempt_id="attempt_2"))
    assert owner.prepare(retry) is context
    assert context.model_context == claim.model_context
    assert context.contributions[0].descriptor.reference == ("static", "1.0.0")
    assert len(adapters["static"].inputs) == 1
    assert log == []
    owner.close_run("thr_1", "run_1")
    assert context.closed
    assert log == ["contribution:static", "handle:static"]
    owner.close()
    assert len(log) == 2


def test_idle_contexts_expire_and_can_be_prepared_again():
    clock = [0.0]
    owner, _ = _owner([], idle_seconds=10, clock=lambda: clock[0])
    claim = _claim()
    context = owner.acquire(claim)
    clock[0] = 20
    assert owner.sweep_idle() == 0  # Active work is protected.
    owner.release(context)
    clock[0] = 31
    assert owner.sweep_idle() == 1
    assert context.closed
    assert owner.resource_counts() == {'retained': 0, 'active': 0}
    restored = owner.acquire(claim)
    assert restored is not context and restored.model_context == context.model_context
    owner.release(restored)
    owner.close()


def test_context_capacity_evicts_idle_lru_and_never_active_work():
    owner, _ = _owner([], max_contexts=2)
    active = owner.acquire(_claim())
    idle = owner.prepare(_claim(thread_id='thr_2', run_id='run_2'))
    third = owner.acquire(_claim(thread_id='thr_3', run_id='run_3'))
    assert idle.closed and not active.closed and not third.closed
    with pytest.raises(RuntimeError, match='capacity'):
        owner.acquire(_claim(thread_id='thr_4', run_id='run_4'))
    assert owner.resource_counts() == {'retained': 2, 'active': 2}
    owner.release(active)
    owner.release(third)
    owner.close()


def test_many_abandoned_threads_keep_constant_context_capacity():
    owner, _ = _owner([], max_contexts=3)
    previous = []
    for index in range(100):
        context = owner.acquire(_claim(thread_id=f'thr_{index}', run_id=f'run_{index}'))
        owner.release(context)
        previous.append(context)
        assert owner.resource_counts()['retained'] <= 3
    assert sum(not context.closed for context in previous) == 3
    owner.close()


def test_empty_selection_does_not_apply_new_catalog_defaults():
    log = []
    owner, adapters = _owner(log)
    context = owner.prepare(_claim(profiles=()))
    assert context.contributions == ()
    assert adapters["static"].inputs == []
    owner.close()
    assert log == []


def test_identical_context_ids_are_isolated_by_thread_and_run():
    owner, _ = _owner([])
    first = owner.prepare(_claim())
    second = owner.prepare(_claim(thread_id="thr_2", run_id="run_2"))
    assert first is not second
    owner.close_run("thr_1", "run_1")
    assert first.closed and not second.closed
    owner.close()


def test_context_identity_drift_is_rejected_before_preparing_again():
    owner, adapters = _owner([])
    claim = _claim()
    original = owner.prepare(claim)
    changed = replace(claim, model_context=replace(claim.model_context, model_revision="revision:sha256:" + "b" * 64))
    with pytest.raises(ValueError, match="snapshot"):
        owner.prepare(changed)
    assert not original.closed
    assert len(adapters["static"].inputs) == 1
    owner.close()


def test_selection_revision_prepares_a_replacement_context_for_the_same_model_context():
    log = []
    owner, _ = _owner(log, second=_Adapter(log))
    first_claim = _claim()
    first = owner.prepare(first_claim)
    changed_claim = replace(
        first_claim,
        attempt=replace(first_claim.attempt, attempt_id="attempt_2"),
        selection_revision="sel_2",
        model_context=replace(
            first_claim.model_context,
            selection_revision="sel_2",
            enabled_profiles=(("static", "1.0.0"), ("extra", "1.0.0")),
        ),
    )

    second = owner.prepare(changed_claim)

    assert second is not first
    assert second.model_context.selection_revision == "sel_2"
    assert len(second.contributions) == 2
    owner.close_run("thr_1", "run_1")
    assert first.closed and second.closed


def test_missing_adapter_is_rejected_before_any_factory_allocates():
    log = []
    owner, _ = _owner(log, seal=False)
    descriptor = ModelCapabilityDescriptor("extra", "1.0.0")
    owner.catalog.register_profile(
        ModelCapabilityProfileInfo(descriptor, "Extra", ("pandapower",)),
        lambda: _Handle(descriptor, log),
    )
    owner.catalog.registry.seal()
    owner.seal()
    with pytest.raises(KeyError):
        owner.prepare(_claim(profiles=(("static", "1.0.0"), descriptor.reference)))
    assert log == []


def test_failed_preparation_rolls_back_every_resource_and_allows_clean_retry():
    log = []
    extra = _Adapter(log, fail=True)
    owner, adapters = _owner(log, second=extra)
    claim = _claim(profiles=(("static", "1.0.0"), ("extra", "1.0.0")))
    with pytest.raises(RuntimeError, match="adapter failed"):
        owner.prepare(claim)
    assert log == ["contribution:static", "handle:extra", "handle:static"]
    extra.fail = False
    context = owner.prepare(claim)
    assert len(context.contributions) == 2
    assert len(adapters["static"].inputs) == 2
    owner.close()


def test_invalid_contribution_is_closed_and_never_cached():
    log = []
    owner, _ = _owner(log, first=_Adapter(log, drift=True))
    with pytest.raises(ValueError, match="snapshot"):
        owner.prepare(_claim())
    assert log == ["contribution:static", "handle:static"]
    owner.close()


def test_cleanup_failure_keeps_original_error_and_attempts_every_close():
    log = []
    owner, _ = _owner(
        log, first=_Adapter(log, fail_close=True), second=_Adapter(log, fail=True),
    )
    with pytest.raises(ExceptionGroup) as error:
        owner.prepare(_claim(profiles=(("static", "1.0.0"), ("extra", "1.0.0"))))
    assert [str(item) for item in error.value.exceptions] == ["adapter failed", "cleanup failed"]
    assert log == ["contribution:static", "handle:extra", "handle:static"]


def test_owner_close_is_idempotent_and_rejects_future_preparation():
    log = []
    owner, _ = _owner(log, first=_Adapter(log, fail_close=True))
    context = owner.prepare(_claim())
    with pytest.raises(ExceptionGroup):
        owner.close()
    assert context.closed
    assert log == ["contribution:static", "handle:static"]
    owner.close()
    with pytest.raises(RuntimeError, match="closed"):
        owner.prepare(_claim())


def test_bootstrap_must_seal_both_registries_before_runtime_preparation():
    owner, _ = _owner([], seal=False)
    with pytest.raises(RuntimeError, match="sealed"):
        owner.prepare(_claim())
    with pytest.raises(RuntimeError, match="sealed"):
        owner.seal()
    owner.catalog.registry.seal()
    owner.seal()
    with pytest.raises(RuntimeError, match="sealed"):
        owner.register_adapter(("static", "1.0.0"), _Adapter([]))


def test_adapter_registration_rejects_unknown_duplicate_and_invalid_entries():
    owner, _ = _owner([], seal=False)
    with pytest.raises(KeyError):
        owner.register_adapter(("unknown", "1.0.0"), _Adapter([]))
    with pytest.raises(ValueError, match="duplicate"):
        owner.register_adapter(("static", "1.0.0"), _Adapter([]))
    descriptor = ModelCapabilityDescriptor("extra", "1.0.0")
    owner.catalog.register_profile(
        ModelCapabilityProfileInfo(descriptor, "Extra", ("pandapower",)),
        lambda: _Handle(descriptor, []),
    )
    with pytest.raises(TypeError):
        owner.register_adapter(descriptor.reference, object())


def test_application_profile_bridge_registers_trusted_factory_and_exposes_profile_to_context():
    log = []
    registry = ModelCapabilityRegistry()
    catalog = CapstoneModelCapabilityCatalog(registry)
    owner = ModelCapabilityContextOwner(catalog)
    descriptor = ModelCapabilityDescriptor("legacy-profile", "1.0.0")
    profile = {"application_id": "legacy", "version": "1"}
    register_application_profile(
        owner, catalog,
        ModelCapabilityProfileInfo(descriptor, "Legacy", ("pandapower",)),
        lambda: profile,
    )
    registry.seal()
    owner.seal()
    context = owner.prepare(_claim(profiles=(descriptor.reference,)))
    contribution = context.contributions[0]
    assert isinstance(contribution, ApplicationProfileCapabilityContribution)
    assert contribution.profile is profile
    assert isinstance(context.handles[0], ApplicationProfileCapabilityHandle)
    owner.close()
    assert context.closed
    del log


def test_application_profile_bridge_prepares_external_runtime_before_context_activation():
    log = []
    registry = ModelCapabilityRegistry()
    catalog = CapstoneModelCapabilityCatalog(registry)
    owner = ModelCapabilityContextOwner(catalog)
    descriptor = ModelCapabilityDescriptor("prepared-profile", "1.0.0")
    profile = {"application_id": "legacy"}

    class Prepared:
        def close(self):
            log.append("prepared:close")

    prepared = Prepared()
    register_application_profile(
        owner, catalog,
        ModelCapabilityProfileInfo(descriptor, "Prepared", ("pandapower",)),
        lambda: profile,
        prepare_profile=lambda selected, context: log.append(
            ("prepared", selected, context.id)
        ) or prepared,
    )
    registry.seal()
    owner.seal()
    context = owner.prepare(_claim(profiles=(descriptor.reference,)))
    contribution = context.contributions[0]
    assert contribution.profile is profile
    assert contribution.prepared is prepared
    assert log == [("prepared", profile, "ctx_1")]
    owner.close()
    assert log[-1] == "prepared:close"


def test_external_profile_preparation_failure_closes_the_allocated_handle():
    log = []
    registry = ModelCapabilityRegistry()
    catalog = CapstoneModelCapabilityCatalog(registry)
    owner = ModelCapabilityContextOwner(catalog)
    descriptor = ModelCapabilityDescriptor("failed-profile", "1.0.0")

    class Profile:
        def close(self):
            log.append("profile:close")

    register_application_profile(
        owner, catalog,
        ModelCapabilityProfileInfo(descriptor, "Failed", ("pandapower",)),
        lambda: Profile(),
        prepare_profile=lambda _profile, _context: (_ for _ in ()).throw(
            RuntimeError("authority preparation failed")
        ),
    )
    registry.seal()
    owner.seal()
    with pytest.raises(RuntimeError, match="authority preparation failed"):
        owner.prepare(_claim(profiles=(descriptor.reference,)))
    assert log == ["profile:close"]


def test_application_profile_bridge_rejects_catalog_mismatch_and_factory_failure():
    owner, _ = _owner([], seal=False)
    other = CapstoneModelCapabilityCatalog(ModelCapabilityRegistry())
    descriptor = ModelCapabilityDescriptor("legacy-profile", "1.0.0")
    with pytest.raises(ValueError, match="same catalog"):
        register_application_profile(
            owner, other,
            ModelCapabilityProfileInfo(descriptor, "Legacy", ("pandapower",)),
            lambda: object(),
        )
    descriptor = ModelCapabilityDescriptor("legacy-profile", "1.0.0")
    register_application_profile(
        owner, owner.catalog,
        ModelCapabilityProfileInfo(descriptor, "Legacy", ("pandapower",)),
        lambda: (_ for _ in ()).throw(RuntimeError("profile factory failed")),
    )
    owner.catalog.registry.seal()
    owner.seal()
    with pytest.raises(RuntimeError, match="profile factory failed"):
        owner.prepare(_claim(profiles=(descriptor.reference,)))
def test_resource_identity_separates_prepared_cache_and_release():
    from dataclasses import replace
    owner, _ = _owner([])
    claim = _claim()
    a = replace(claim, submission={'professional_resource': {'profile_revision': 'A'}})
    b = replace(claim, submission={'professional_resource': {'profile_revision': 'B'}})
    first = owner.acquire(a)
    second = owner.acquire(b)
    assert first is not second
    assert owner.acquire(a) is first
    assert owner.resource_counts() == {'retained': 2, 'active': 2}
    owner.release(first)
    owner.release(first)
    assert not first.closed and not second.closed
    owner.release(second)
    owner.close()
    assert first.closed and second.closed
