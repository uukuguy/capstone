"""Process-local preparation of exact Model Capability contributions.

The Thread ledger stores only identities.  This module owns the corresponding
short-lived resources for one active model context and deliberately knows
nothing about a Domain Pack, Authority, Pi, or DSH implementation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
import time
from threading import RLock
from typing import Protocol, runtime_checkable

from capstone_model_capability_spi import (
    ModelCapabilityDescriptor,
    ModelCapabilityProfileHandle,
    ModelCapabilitySelection,
)

from .model_capability import CapstoneModelCapabilityCatalog, ModelCapabilityProfileInfo
from .thread_protocol import ModelContextSnapshot
from .thread_service import AttemptClaim, ThreadModelDescriptor


@runtime_checkable
class PreparedModelCapabilityContribution(Protocol):
    """A trusted profile contribution borrowed by Harness for a context."""

    descriptor: ModelCapabilityDescriptor
    model_context: ModelContextSnapshot

    def close(self) -> None: ...


@runtime_checkable
class ModelCapabilityAdapter(Protocol):
    """Prepare one exact registered profile against an immutable context."""

    descriptor: ModelCapabilityDescriptor

    def prepare(
        self,
        handle: ModelCapabilityProfileHandle,
        *,
        model_context: ModelContextSnapshot,
    ) -> PreparedModelCapabilityContribution: ...


@dataclass(slots=True)
class ApplicationProfileCapabilityHandle:
    """Bridge handle for a legacy Kernel ``ApplicationProfile`` object.

    The type is intentionally structural: ``capstone-agent`` does not import
    the Kernel's application classes.  The selected application may retain the
    object as a declaration and prepare its authority/runtime resources later.
    """

    descriptor: ModelCapabilityDescriptor
    profile: object
    _closed: bool = False

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close = getattr(self.profile, "close", None)
        if callable(close):
            close()


@dataclass(slots=True)
class ApplicationProfileCapabilityContribution:
    """Context contribution carrying one application profile declaration."""

    descriptor: ModelCapabilityDescriptor
    model_context: ModelContextSnapshot
    profile: object
    prepared: object
    _closed: bool = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        # The handle owns the profile declaration; the contribution owns the
        # external workspace/credential/Authority preparation result.
        if self.prepared is self.profile:
            return
        close = getattr(self.prepared, "close", None)
        if callable(close):
            close()


class ApplicationProfileCapabilityAdapter:
    """Adapt the bridge handle into a context-scoped profile contribution."""

    def __init__(
        self,
        descriptor: ModelCapabilityDescriptor,
        *,
        prepare_profile: Callable[[object, ModelContextSnapshot], object] | None = None,
    ) -> None:
        self.descriptor = descriptor
        if prepare_profile is not None and not callable(prepare_profile):
            raise TypeError("prepare_profile must be callable")
        self._prepare_profile = prepare_profile

    def prepare(
        self,
        handle: ModelCapabilityProfileHandle,
        *,
        model_context: ModelContextSnapshot,
    ) -> ApplicationProfileCapabilityContribution:
        if not isinstance(handle, ApplicationProfileCapabilityHandle):
            raise TypeError("application profile handle is invalid")
        if handle.closed:
            raise RuntimeError("application profile handle is closed")
        prepared = (
            handle.profile
            if self._prepare_profile is None
            else self._prepare_profile(handle.profile, model_context)
        )
        return ApplicationProfileCapabilityContribution(
            self.descriptor, model_context, handle.profile, prepared,
        )


def register_application_profile(
    owner: "ModelCapabilityContextOwner",
    catalog: CapstoneModelCapabilityCatalog,
    info: ModelCapabilityProfileInfo,
    profile_factory: Callable[[], object],
    *,
    trust_source: str = "trusted-application-bootstrap",
    prepare_profile: Callable[[object, ModelContextSnapshot], object] | None = None,
) -> None:
    """Register one externally assembled legacy profile without domain imports."""

    if owner.catalog is not catalog:
        raise ValueError("owner and catalog must use the same catalog")
    if not callable(profile_factory):
        raise TypeError("profile_factory must be callable")
    catalog.register_profile(
        info,
        lambda: ApplicationProfileCapabilityHandle(
            info.descriptor, profile_factory(),
        ),
        trust_source=trust_source,
    )
    owner.register_adapter(
        info.descriptor.reference,
        ApplicationProfileCapabilityAdapter(
            info.descriptor, prepare_profile=prepare_profile,
        ),
    )


@dataclass(slots=True)
class PreparedModelCapabilityContext:
    """Run-owned prepared resources for one exact model context snapshot."""

    thread_id: str
    run_id: str
    model_context: ModelContextSnapshot
    handles: tuple[ModelCapabilityProfileHandle, ...]
    contributions: tuple[PreparedModelCapabilityContribution, ...]
    _closed: bool = False

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        errors: list[BaseException] = []
        for resource in (*reversed(self.contributions), *reversed(self.handles)):
            try:
                resource.close()
            except BaseException as error:
                errors.append(error)
        if errors:
            raise BaseExceptionGroup("model capability context cleanup failed", errors)


class ModelCapabilityContextOwner:
    """Prepare and retain contexts by exact Thread/Run/model identity.

    Registry and adapter registration are bootstrap operations.  ``seal`` must
    run before a worker can prepare anything.  A claimed Attempt can reuse its
    Run context, but any snapshot drift fails closed.
    """

    def __init__(self, catalog: CapstoneModelCapabilityCatalog, *,
                 max_contexts: int | None = None, idle_seconds: float | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if not isinstance(catalog, CapstoneModelCapabilityCatalog):
            raise TypeError("catalog must be a CapstoneModelCapabilityCatalog")
        self.catalog = catalog
        self.max_contexts = int(os.environ.get('CAPSTONE_THREAD_CONTEXT_LIMIT', '4')) if max_contexts is None else max_contexts
        self.idle_seconds = float(os.environ.get('CAPSTONE_THREAD_CONTEXT_IDLE_SECONDS', '60')) if idle_seconds is None else idle_seconds
        if not 1 <= self.max_contexts <= 64 or not 1 <= self.idle_seconds <= 86400:
            raise ValueError('model capability resource limits are invalid')
        self._clock = clock
        self._adapters: dict[tuple[str, str], ModelCapabilityAdapter] = {}
        self._contexts: dict[tuple[str, str, str, str], PreparedModelCapabilityContext] = {}
        self._usage: dict[tuple[str, str, str, str], tuple[int, float]] = {}
        self._resource_counts = (0, 0)
        self._sealed = False
        self._closed = False
        self._lock = RLock()

    @property
    def sealed(self) -> bool:
        return self._sealed

    def register_adapter(
        self,
        reference: tuple[str, str],
        adapter: ModelCapabilityAdapter,
    ) -> None:
        with self._lock:
            if self._sealed:
                raise RuntimeError("model capability context owner is sealed")
            if not self.catalog.registry.is_registered(reference):
                raise KeyError(reference)
            if reference in self._adapters:
                raise ValueError("duplicate model capability adapter")
            descriptor = getattr(adapter, "descriptor", None)
            if not isinstance(descriptor, ModelCapabilityDescriptor):
                raise TypeError("model capability adapter descriptor is invalid")
            if descriptor.reference != reference:
                raise ValueError("model capability adapter descriptor does not match")
            if not callable(getattr(adapter, "prepare", None)):
                raise TypeError("model capability adapter is not preparable")
            self._adapters[reference] = adapter

    def seal(self) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("model capability context owner is closed")
            if not self.catalog.registry.sealed:
                raise RuntimeError("model capability registry must be sealed first")
            self._sealed = True

    def prepare(self, claim: AttemptClaim) -> PreparedModelCapabilityContext:
        if not isinstance(claim, AttemptClaim):
            raise TypeError("claim must be an AttemptClaim")
        model_context = claim.model_context
        key = (
            claim.thread_id, claim.run_id, model_context.id,
            model_context.selection_revision,
        )
        references = tuple(model_context.enabled_profiles)
        with self._lock:
            if self._closed:
                raise RuntimeError("model capability context owner is closed")
            if not self._sealed:
                raise RuntimeError("model capability context owner is not sealed")
            self._sweep_idle_locked()
            existing = self._contexts.get(key)
            if existing is not None:
                if existing.model_context != model_context:
                    raise ValueError("model capability context snapshot drift")
                pins, _ = self._usage[key]
                self._usage[key] = pins, self._clock()
                return existing
            missing = [reference for reference in references if reference not in self._adapters]
            if missing:
                raise KeyError(missing[0])
            if len(self._contexts) >= self.max_contexts:
                idle = [(last_used, cached_key) for cached_key, (pins, last_used) in self._usage.items() if pins == 0]
                if not idle:
                    raise RuntimeError('model capability context capacity is full')
                self._evict_locked(min(idle)[1])

            selection = ModelCapabilitySelection(references)
            handles = self.catalog.prepare(
                ThreadModelDescriptor(
                    model_context.model_id,
                    model_context.model_revision,
                    model_context.implementation_family,
                ),
                selection,
            )
            contributions: list[PreparedModelCapabilityContribution] = []
            try:
                for reference, handle in zip(references, handles, strict=True):
                    adapter = self._adapters[reference]
                    contribution = adapter.prepare(handle, model_context=model_context)
                    self._validate_contribution(contribution, reference, model_context)
                    contributions.append(contribution)
                context = PreparedModelCapabilityContext(
                    claim.thread_id, claim.run_id, model_context,
                    tuple(handles), tuple(contributions),
                )
                self._contexts[key] = context
                self._usage[key] = 0, self._clock()
                self._publish_resource_counts_locked()
                return context
            except BaseException as error:
                cleanup = _close_resources((*reversed(contributions), *reversed(handles)))
                if cleanup:
                    raise BaseExceptionGroup(
                        "model capability preparation and cleanup failed",
                        [error, *cleanup],
                    ) from None
                raise

    def acquire(self, claim: AttemptClaim) -> PreparedModelCapabilityContext:
        """Pin resources until the Attempt releases them, including blocked work."""
        with self._lock:
            context = self.prepare(claim)
            key = (context.thread_id, context.run_id, context.model_context.id, context.model_context.selection_revision)
            pins, last_used = self._usage[key]
            self._usage[key] = pins + 1, last_used
            self._publish_resource_counts_locked()
            return context

    def release(self, context: PreparedModelCapabilityContext) -> None:
        with self._lock:
            key = (context.thread_id, context.run_id, context.model_context.id, context.model_context.selection_revision)
            if self._contexts.get(key) is not context:
                return
            pins, last_used = self._usage[key]
            if pins < 1:
                raise RuntimeError('model capability context is not acquired')
            self._usage[key] = pins - 1, self._clock() if pins == 1 else last_used
            self._publish_resource_counts_locked()

    def resource_counts(self) -> dict[str, int]:
        """Read published counts without waiting for preparation or cleanup IO."""
        retained, active = self._resource_counts
        return {'retained': retained, 'active': active}

    def _publish_resource_counts_locked(self) -> None:
        self._resource_counts = (
            len(self._contexts), sum(pins > 0 for pins, _ in self._usage.values()),
        )

    def sweep_idle(self) -> int:
        with self._lock:
            return self._sweep_idle_locked()

    def _sweep_idle_locked(self) -> int:
        now = self._clock()
        expired = [key for key, (pins, last_used) in self._usage.items()
                   if pins == 0 and now - last_used >= self.idle_seconds]
        errors: list[BaseException] = []
        for key in expired:
            try:
                self._evict_locked(key)
            except BaseException as error:
                errors.extend(_flatten_group(error))
        if errors:
            raise BaseExceptionGroup('idle model capability cleanup failed', errors)
        return len(expired)

    def _evict_locked(self, key: tuple[str, str, str, str]) -> None:
        context = self._contexts.pop(key)
        del self._usage[key]
        self._publish_resource_counts_locked()
        context.close()

    def close_run(self, thread_id: str, run_id: str) -> None:
        with self._lock:
            contexts = [
                (key, context) for key, context in self._contexts.items()
                if key[:2] == (thread_id, run_id)
            ]
            if any(self._usage[key][0] for key, _ in contexts):
                raise RuntimeError('model capability context is active')
            for key, _ in contexts:
                del self._contexts[key]
                del self._usage[key]
            self._publish_resource_counts_locked()
        errors: list[BaseException] = []
        for _, context in contexts:
            try:
                context.close()
            except BaseException as error:
                errors.extend(_flatten_group(error))
        if errors:
            raise BaseExceptionGroup("model capability run cleanup failed", errors)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            contexts = tuple(self._contexts.values())
            self._contexts.clear()
            self._usage.clear()
            self._publish_resource_counts_locked()
        errors: list[BaseException] = []
        for context in contexts:
            try:
                context.close()
            except BaseException as error:
                errors.extend(_flatten_group(error))
        if errors:
            raise BaseExceptionGroup("model capability owner cleanup failed", errors)

    @staticmethod
    def _validate_contribution(
        contribution: object,
        reference: tuple[str, str],
        model_context: ModelContextSnapshot,
    ) -> None:
        descriptor = getattr(contribution, "descriptor", None)
        if not isinstance(descriptor, ModelCapabilityDescriptor) or descriptor.reference != reference:
            _close_one(contribution)
            raise ValueError("prepared contribution descriptor does not match")
        if getattr(contribution, "model_context", None) != model_context:
            _close_one(contribution)
            raise ValueError("prepared contribution model context snapshot drift")
        if not callable(getattr(contribution, "close", None)):
            raise TypeError("prepared contribution is not closeable")


def _close_one(resource: object) -> None:
    close = getattr(resource, "close", None)
    if callable(close):
        close()


def _close_resources(resources: tuple[object, ...]) -> list[BaseException]:
    errors: list[BaseException] = []
    for resource in resources:
        try:
            _close_one(resource)
        except BaseException as error:
            errors.append(error)
    return errors


def _flatten_group(error: BaseException) -> list[BaseException]:
    if isinstance(error, BaseExceptionGroup):
        values: list[BaseException] = []
        for nested in error.exceptions:
            values.extend(_flatten_group(nested))
        return values
    return [error]


__all__ = [
    "ApplicationProfileCapabilityAdapter",
    "ApplicationProfileCapabilityContribution",
    "ApplicationProfileCapabilityHandle",
    "ModelCapabilityAdapter",
    "ModelCapabilityContextOwner",
    "PreparedModelCapabilityContext",
    "PreparedModelCapabilityContribution",
    "register_application_profile",
]
