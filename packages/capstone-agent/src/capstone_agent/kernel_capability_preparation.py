"""Application-private preparation of legacy Kernel profiles for Thread Contexts.

This bridge is the last place that knows the Kernel ``ApplicationProfile``
shape.  It returns a process-local prepared resource; Thread snapshots carry
only the model identity and opaque references.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import re
from pathlib import Path
from threading import RLock
from typing import Any

from capability_agent.application.composition import prepare_application
from capability_agent.application.composition import CredentialBroker
from capability_agent.application.profile import ApplicationProfile
from capability_agent.application.workspace import ApplicationWorkspace

from .application import EmptyCredentialBroker, domain_registry
from .thread_protocol import ModelContextSnapshot
from .model_identity import validate_model_id


_REVISION = re.compile(r"^revision:[a-z0-9_-]+:[0-9a-f]{16,128}$")
_REFERENCE = re.compile(r"^[a-z][a-z0-9_-]{0,63}:[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")


@dataclass(frozen=True, slots=True)
class AuthorityModelBinding:
    """Bound model identity returned by an application-owned Authority resolver."""

    binding_id: str
    model_id: str
    model_revision: str
    implementation_family: str
    context_ref: str
    model_reference_verifier: Callable[[str], bool] | None = field(default=None, repr=False, compare=False)
    context_identity_verifier: Callable[[str, str], bool] | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        for name, value in (
            ("binding_id", self.binding_id),
            ("implementation_family", self.implementation_family),
        ):
            if not isinstance(value, str) or not re.fullmatch(
                r"[a-z][a-z0-9_-]{0,63}", value
            ):
                raise ValueError(f"Authority model {name} is invalid")
        validate_model_id(self.model_id)
        if not isinstance(self.model_revision, str) or not _REVISION.fullmatch(self.model_revision):
            raise ValueError("Authority model revision is invalid")
        if not isinstance(self.context_ref, str) or not _REFERENCE.fullmatch(self.context_ref):
            raise ValueError("Authority model reference is invalid")
        if self.model_reference_verifier is not None and not callable(self.model_reference_verifier):
            raise TypeError("Authority model reference verifier must be callable")
        if self.context_identity_verifier is not None and not callable(self.context_identity_verifier):
            raise TypeError('Authority context identity verifier must be callable')

    def accepts_context_identity(self, reference: str, revision: str) -> bool:
        if not isinstance(reference, str) or not _REFERENCE.fullmatch(reference):
            return False
        if not isinstance(revision, str) or not _REVISION.fullmatch(revision):
            return False
        if (reference, revision) == (self.context_ref, self.model_revision):
            return True
        if self.context_identity_verifier is None:
            return False
        try:
            return self.context_identity_verifier(reference, revision) is True
        except Exception:
            return False

    def accepts_model_reference(self, reference: str) -> bool:
        """Admit the bound reference or an application-verified related model."""
        if not isinstance(reference, str) or not _REFERENCE.fullmatch(reference):
            return False
        if reference == self.context_ref:
            return True
        verifier = self.model_reference_verifier
        if verifier is None:
            return False
        try:
            return verifier(reference) is True
        except Exception:
            return False


@dataclass(slots=True)
class PreparedKernelApplicationProfile:
    """Closeable Context resource containing prepared Kernel bindings."""

    profile: ApplicationProfile
    prepared_application: object
    workspace: ApplicationWorkspace
    model_binding: AuthorityModelBinding
    _closed: bool = False
    _lock: RLock = field(default_factory=RLock, repr=False)

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        bindings = getattr(self.prepared_application, "bindings", None)
        values = tuple(bindings.values()) if isinstance(bindings, Mapping) else ()
        errors: list[BaseException] = []
        for binding in reversed(values):
            endpoint = getattr(binding, "endpoint", None)
            close = getattr(endpoint, "close", None)
            if not callable(close):
                continue
            try:
                close()
            except BaseException as error:
                errors.append(error)
        if errors:
            raise BaseExceptionGroup("prepared application cleanup failed", errors)


class KernelApplicationProfilePreparer:
    """Prepare a selected Kernel profile and bind it to an Authority model."""

    def __init__(
        self,
        *,
        workspace_root: Path,
        model_binder: Callable[[object, ModelContextSnapshot], AuthorityModelBinding],
        credentials: CredentialBroker | None = None,
    ) -> None:
        if not isinstance(workspace_root, Path):
            raise TypeError("workspace_root must be a Path")
        if not callable(model_binder):
            raise TypeError("model_binder must be callable")
        self.workspace_root = workspace_root
        self.model_binder = model_binder
        self.credentials: CredentialBroker = (
            credentials if credentials is not None else EmptyCredentialBroker()
        )

    def __call__(
        self,
        profile: ApplicationProfile,
        model_context: ModelContextSnapshot,
    ) -> PreparedKernelApplicationProfile:
        if not isinstance(profile, ApplicationProfile):
            raise TypeError("profile must be an ApplicationProfile")
        if not isinstance(model_context, ModelContextSnapshot):
            raise TypeError("model_context must be a ModelContextSnapshot")
        binding_ids = tuple(binding.binding_id for binding in profile.domains)
        workspace = ApplicationWorkspace.create(
            self.workspace_root,
            binding_ids=binding_ids,
        )
        prepared = prepare_application(
            profile,
            registry=domain_registry(profile),
            workspace=workspace.root,
            credentials=self.credentials,
        )
        try:
            model_binding = self.model_binder(prepared, model_context)
            self._validate_binding(model_binding, profile, model_context, prepared)
            return PreparedKernelApplicationProfile(
                profile=profile,
                prepared_application=prepared,
                workspace=workspace,
                model_binding=model_binding,
            )
        except BaseException as error:
            cleanup = _close_prepared(prepared)
            if cleanup:
                raise BaseExceptionGroup(
                    "model binding and application cleanup failed",
                    [error, *cleanup],
                ) from None
            raise

    @staticmethod
    def _validate_binding(
        binding: object,
        profile: ApplicationProfile,
        context: ModelContextSnapshot,
        prepared: object,
    ) -> None:
        if not isinstance(binding, AuthorityModelBinding):
            raise TypeError("model binder returned an invalid binding")
        expected_ids = {item.binding_id for item in profile.domains}
        if binding.binding_id not in expected_ids:
            raise ValueError("Authority model binding is not selected by profile")
        if (
            binding.model_id != context.model_id
            or binding.model_revision != context.model_revision
            or binding.implementation_family != context.implementation_family
        ):
            raise ValueError("Authority model binding does not match Thread snapshot")
        bindings = getattr(prepared, "bindings", None)
        if not isinstance(bindings, Mapping) or binding.binding_id not in bindings:
            raise ValueError("Authority model binding has no prepared application binding")


def _close_prepared(prepared: object) -> list[BaseException]:
    bindings = getattr(prepared, "bindings", None)
    values = tuple(bindings.values()) if isinstance(bindings, Mapping) else ()
    errors: list[BaseException] = []
    for binding in reversed(values):
        close = getattr(getattr(binding, "endpoint", None), "close", None)
        if not callable(close):
            continue
        try:
            close()
        except BaseException as error:
            errors.append(error)
    return errors


__all__ = [
    "AuthorityModelBinding",
    "KernelApplicationProfilePreparer",
    "PreparedKernelApplicationProfile",
]
