from __future__ import annotations

import pypsa_agent.hosted as hosted
import pypsa_agent.hosted_worker as hosted_worker


def test_registered_pypsa_thread_application_uses_the_capstone_host() -> None:
    assembly = hosted.build_registered_pypsa_thread_application()

    assert assembly.catalog.default_model_id == "regional-six-bus"
    assert "regional-six-bus" in assembly.catalog.list_model_ids()
    assert any(
        profile.descriptor.profile_id == "pypsa-business-cases"
        for profile in assembly.capability_catalog.profiles_for_family("pypsa")
    )


def test_pypsa_model_resolver_returns_stable_authority_revision() -> None:
    resolver = hosted.RegisteredPyPSAThreadCatalog()

    record = resolver.resolve("regional-six-bus")

    assert record.model_id == "regional-six-bus"
    assert record.model_revision.startswith("revision:sha256:")
    assert len(record.model_revision.rsplit(":", 1)[-1]) == 64
    assert record.implementation_family == "pypsa"


def test_hosted_entrypoints_delegate_to_capstone(monkeypatch) -> None:
    sentinel = object()
    seen: list[object] = []

    monkeypatch.setattr(hosted, "build_registered_pypsa_thread_application", lambda: sentinel)
    monkeypatch.setattr(hosted, "run_hosted_api", lambda factory: seen.append(factory()) or 17)
    assert hosted.main() == 17
    assert seen == [sentinel]


def test_hosted_worker_entrypoint_delegates_to_capstone(monkeypatch) -> None:
    sentinel = object()
    seen: list[object] = []

    monkeypatch.setattr(
        hosted_worker,
        "build_registered_pypsa_thread_application",
        lambda: sentinel,
    )
    monkeypatch.setattr(
        hosted_worker,
        "run_hosted_worker",
        lambda factory: seen.append(factory()) or 23,
    )

    assert hosted_worker.main() == 23
    assert seen == [sentinel]
