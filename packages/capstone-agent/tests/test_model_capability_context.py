from __future__ import annotations

from dataclasses import replace

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


def _owner(log, *, second=None, first=None, seal=True):
    registry = ModelCapabilityRegistry()
    catalog = CapstoneModelCapabilityCatalog(registry)
    owner = ModelCapabilityContextOwner(catalog)
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
