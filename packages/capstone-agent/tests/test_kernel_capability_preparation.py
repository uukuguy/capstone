from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from capability_agent.application.manifest import ApplicationManifest
from capability_agent.application.output import JsonOutputRenderer
from capability_agent.application.profile import (
    ApplicationProfile, CredentialScope, DataSharingPolicy, DomainBinding,
)
from capstone_agent import kernel_capability_preparation as preparation
from capstone_agent.kernel_capability_preparation import (
    AuthorityModelBinding, KernelApplicationProfilePreparer,
)
from capstone_agent.thread_protocol import ModelContextSnapshot


def _context():
    return ModelContextSnapshot(
        "ctx_1", "model_1", "revision:sha256:" + "a" * 64, "family", "sel_1",
    )


def _profile():
    domain = SimpleNamespace(missing_application_components=lambda: ())
    return ApplicationProfile(
        ApplicationManifest("test", "1.0", "Test", "ctx/1", "out/1", "art/1", "agent_"),
        (DomainBinding("model", "model_", domain, CredentialScope(), DataSharingPolicy()),),
        JsonOutputRenderer(), object(), object(), object(),
    )


def _install_preparation(monkeypatch, log, *, failed_close=False):
    bindings = {}
    for name in ("model", "other"):
        def close(name=name):
            log.append("close:" + name)
            if failed_close and name == "other":
                raise RuntimeError("endpoint cleanup failed")
        bindings[name] = SimpleNamespace(endpoint=SimpleNamespace(close=close))
    result = SimpleNamespace(bindings=bindings)
    calls = []
    monkeypatch.setattr(preparation, "domain_registry", lambda _profile: "registry")
    def prepare(profile, **kwargs):
        calls.append((profile, kwargs))
        return result
    monkeypatch.setattr(preparation, "prepare_application", prepare)
    return calls, result


def _binding(context):
    return AuthorityModelBinding(
        "model", context.model_id, context.model_revision,
        context.implementation_family, "context:sha256:" + "b" * 64,
    )


def test_preparer_binds_pinned_model_and_creates_exclusive_workspace(tmp_path, monkeypatch):
    log = []
    calls, prepared = _install_preparation(monkeypatch, log)
    credentials = object()
    received = []
    binder = lambda application, context: received.append((application, context)) or _binding(context)
    preparer = KernelApplicationProfilePreparer(
        workspace_root=tmp_path, model_binder=binder, credentials=credentials,
    )
    profile = _profile()
    first = preparer(profile, _context())
    second = preparer(profile, _context())
    assert first.workspace.root != second.workspace.root
    assert first.prepared_application is prepared
    assert first.model_binding.model_revision == _context().model_revision
    assert received == [(prepared, _context()), (prepared, _context())]
    assert calls[0][1]["credentials"] is credentials
    assert calls[0][1]["registry"] == "registry"
    assert calls[0][1]["workspace"] == first.workspace.root
    assert first.workspace.domain_path("model").is_dir()
    first.close()
    first.close()
    assert log == ["close:other", "close:model"]
    assert first.closed
    assert first.workspace.root.is_dir()
    second.close()


@pytest.mark.parametrize("field,value", [
    ("model_id", "another"), ("model_revision", "revision:sha256:" + "c" * 64),
    ("implementation_family", "another"), ("binding_id", "missing"),
])
def test_preparer_rejects_foreign_model_and_closes_all_endpoints(tmp_path, monkeypatch, field, value):
    log = []
    _install_preparation(monkeypatch, log)
    preparer = KernelApplicationProfilePreparer(
        workspace_root=tmp_path,
        model_binder=lambda _, context: replace(_binding(context), **{field: value}),
    )
    with pytest.raises(ValueError, match="binding"):
        preparer(_profile(), _context())
    assert log == ["close:other", "close:model"]


def test_model_binding_failure_preserves_original_and_cleanup_errors(tmp_path, monkeypatch):
    log = []
    _install_preparation(monkeypatch, log, failed_close=True)
    def bind(*_):
        raise RuntimeError("model binding failed")
    preparer = KernelApplicationProfilePreparer(workspace_root=tmp_path, model_binder=bind)
    with pytest.raises(ExceptionGroup) as error:
        preparer(_profile(), _context())
    assert [str(item) for item in error.value.exceptions] == [
        "model binding failed", "endpoint cleanup failed",
    ]
    assert log == ["close:other", "close:model"]


def test_invalid_profile_fails_before_workspace_or_authority_allocation(tmp_path):
    called = []
    preparer = KernelApplicationProfilePreparer(
        workspace_root=tmp_path / "unused", model_binder=lambda *_: called.append(True),
    )
    with pytest.raises(TypeError, match="ApplicationProfile"):
        preparer(object(), _context())
    assert called == []
    assert not (tmp_path / "unused").exists()


@pytest.mark.parametrize("reference", ["", "/tmp/raw.json", "https://example.com", object()])
def test_authority_binding_only_accepts_opaque_content_references(reference):
    with pytest.raises(ValueError, match="reference"):
        AuthorityModelBinding("model", "model_1", _context().model_revision, "family", reference)
