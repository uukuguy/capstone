"""Application-owned capacity, selected once at process initialization.

Consumers use ``limits`` at execution time. Importing a numeric default must
not prevent an application from selecting a larger profile at startup.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from types import MappingProxyType


SCHEMA = 'capstone-capacity-profile/1'
_SOURCE = Path(__file__).parent / 'resources' / 'application-capacity.json'


@dataclass(frozen=True)
class CapacityProfile:
    values: Mapping[str, int]
    fingerprint: str
    mode: str = 'normal'

    def to_document(self) -> dict:
        return {'schema': SCHEMA, 'limits': dict(self.values), 'fingerprint': self.fingerprint,
                'mode': self.mode}


class CapacityExceeded(ValueError):
    def __init__(self, dimension: str, actual: int, limit: int, phase: str | None = None,
                 *, mode: str = 'normal'):
        self.dimension, self.actual, self.limit, self.phase = dimension, actual, limit, phase
        self.mode = mode
        super().__init__(f'capacity_exceeded: {dimension}; actual={actual}; limit={limit}'
                         + (f'; phase={phase}' if phase else ''))

    def to_document(self) -> dict:
        document = {'code': 'capacity_exceeded', 'dimension': self.dimension,
                'actual': self.actual, 'limit': self.limit, 'phase': self.phase,
                'unit': ('bytes' if self.dimension.endswith('_bytes') else
                         'seconds' if self.dimension.endswith('_seconds') else 'items'),
                'retryable': False}
        if self.mode == 'debug':
            document.update(mode='debug', fatal=True, effective=self.limit,
                            source='application_capacity', location=self.phase)
        return document


def _profile(overrides=None, *, mode=None) -> CapacityProfile:
    base = json.loads(_SOURCE.read_text(encoding='utf-8'))['limits']
    selected_mode = 'normal'
    if overrides is not None:
        if isinstance(overrides, CapacityProfile):
            overrides = overrides.to_document()
        if not isinstance(overrides, Mapping):
            raise ValueError('capacity overrides must be an object')
        if 'schema' in overrides:
            if overrides['schema'] != SCHEMA or set(overrides) - {'schema', 'limits', 'fingerprint', 'mode'}:
                raise ValueError('capacity profile schema is invalid')
            selected_mode = overrides.get('mode', 'normal')
            overrides = overrides.get('limits')
        if not isinstance(overrides, Mapping) or set(overrides) - set(base):
            raise ValueError('capacity profile contains unknown limits')
        base.update(overrides)
    for key, value in base.items():
        if type(value) is not int or value < (0 if key == 'provider_stream_bytes' else 1):
            raise ValueError(f'capacity limit is invalid: {key}')
        # The same document is consumed by JavaScript without precision loss.
        if value > 9007199254740991:
            raise ValueError(f'capacity limit exceeds exact integer range: {key}')
    for smaller, larger in (
        ('upload_chunk_bytes', 'upload_chunk_max_bytes'),
        ('upload_chunk_max_bytes', 'upload_file_bytes'),
        ('upload_file_bytes', 'upload_session_bytes'),
        ('artifact_file_bytes', 'native_storage_bytes'),
        ('native_context_bytes', 'native_task_bytes'),
        ('model_output_tokens', 'model_context_tokens'),
    ):
        if base[smaller] > base[larger]:
            raise ValueError(f'capacity {smaller} exceeds {larger}')
    selected_mode = selected_mode if mode is None else mode
    if selected_mode not in ('normal', 'debug'):
        raise ValueError('capacity mode must be normal or debug')
    encoded = json.dumps({'limits': base, 'mode': selected_mode}, sort_keys=True, separators=(',', ':')).encode()
    return CapacityProfile(MappingProxyType(base), sha256(encoded).hexdigest(), selected_mode)


_current: CapacityProfile | None = None


def initialize_capacity(overrides=None, *, environment=None, mode=None) -> CapacityProfile:
    """Select defaults plus one optional JSON/file source and explicit overrides.

    Call before starting requests or workers. Reinitialization exists for an
    application's next startup and isolated tests, never as a per-turn option.
    """
    global _current
    environment = {} if environment is None else environment
    raw, file = environment.get('CAPSTONE_CAPACITY_JSON'), environment.get('CAPSTONE_CAPACITY_FILE')
    if raw and file:
        raise ValueError('capacity configuration source is ambiguous')
    document = json.loads(raw) if raw else json.loads(Path(file).read_text()) if file else None
    selected = _profile(document, mode=environment.get('CAPSTONE_CAPACITY_MODE'))
    if overrides is not None:
        explicit = overrides.to_document() if isinstance(overrides, CapacityProfile) else overrides
        _profile(explicit)
        if not isinstance(explicit, Mapping):
            raise ValueError('capacity overrides must be an object')
        additions = explicit.get('limits', explicit)
        selected = _profile({**selected.values, **additions},
                            mode=explicit.get('mode', selected.mode))
    if mode is not None:
        selected = _profile(selected, mode=mode)
    _current = selected
    try:
        from capability_agent.runtime.capacity import initialize_runtime_limits
    except ModuleNotFoundError as error:
        if error.name not in {'capability_agent', 'capability_agent.runtime', 'capability_agent.runtime.capacity'}:
            raise
    else:
        initialize_runtime_limits(selected.values, mode=selected.mode)
    return selected


def current_capacity() -> CapacityProfile:
    global _current
    if _current is None:
        _current = _profile()
    return _current


class _Limits:
    __slots__ = ()

    def __getattr__(self, field: str) -> int:
        try:
            return current_capacity().values[field]
        except KeyError:
            raise AttributeError(field) from None


limits = _Limits()


def require_capacity(field: str, actual: int, phase: str | None = None) -> None:
    maximum = getattr(limits, field)
    if actual > maximum and not (field == 'provider_stream_bytes' and maximum == 0):
        raise CapacityExceeded(field, actual, maximum, phase, mode=current_capacity().mode)


def observe_capacity(field: str, actual: int, phase: str | None = None) -> bool:
    """Report a soft exceedance; debug mode interrupts before recovery."""
    maximum = getattr(limits, field)
    exceeded = actual > maximum and not (field == 'provider_stream_bytes' and maximum == 0)
    if exceeded and current_capacity().mode == 'debug':
        raise CapacityExceeded(field, actual, maximum, phase, mode='debug')
    return exceeded
