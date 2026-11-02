"""Neutral initialization limits. Applications supply their resolved profile."""
from collections.abc import Mapping
from types import MappingProxyType

DEFAULT_RUNTIME_LIMITS = MappingProxyType({
    'control_document_bytes': 33554432, 'rpc_frame_bytes': 8388608, 'rpc_batch_requests': 128,
    'tool_timeout_seconds': 1800, 'tool_observation_bytes': 4194304,
    'research_request_bytes': 67108864, 'research_response_bytes': 268435456,
    'research_claim_count': 512, 'research_note_count': 1024, 'research_question_count': 256,
    'research_text_chars': 33554432, 'research_summary_chars': 65536, 'context_references': 4096,
    'research_goal_chars': 65536, 'research_progress_chars': 16384, 'research_page_records': 512,
    'guide_resource_count': 512, 'guide_document_bytes': 4194304, 'guide_total_bytes': 33554432,
    'guide_title_chars': 4096, 'decision_text_chars': 65536, 'decision_references': 4096,
    'diagnostic_tail_bytes': 1048576,
    'context_segment_bytes':67108864,'context_manifest_bytes':1048576,'answer_summary_chars':4096,
    'diagnostic_error_count':128,'diagnostic_path_parts':64,'diagnostic_path_chars':4096,
    'diagnostic_text_chars':16384,'context_marker_bytes':1048576,
    'research_round_count':64,'research_finding_count':4096,'research_snapshot_bytes':16777216,
})
_initialized = DEFAULT_RUNTIME_LIMITS
_mode = 'normal'


def runtime_limits(overrides: Mapping[str, int] | None = None) -> Mapping[str, int]:
    result = dict(_initialized)
    if overrides is not None:
        if not isinstance(overrides, Mapping):
            raise ValueError('runtime_limits must be a mapping')
        for name, value in overrides.items():
            if (not isinstance(name, str) or type(value) is not int
                    or value < (0 if name == 'provider_stream_bytes' else 1) or value > 2**53 - 1):
                raise ValueError(f'invalid runtime capacity: {name}')
            result[name] = value
    return MappingProxyType(result)


def initialize_runtime_limits(overrides: Mapping[str,int] | None = None, *, mode: str = 'normal') -> Mapping[str,int]:
    """Application startup injection for helpers without a runtime object.

    Constructed controllers/transports retain their own immutable snapshot.
    No configuration files or Application imports are involved.
    """
    global _initialized, _mode
    if mode not in {'normal', 'debug'}:
        raise ValueError('runtime limit mode must be normal or debug')
    resolved=runtime_limits(overrides)
    _initialized, _mode=resolved, mode
    return _initialized


def runtime_limit_mode() -> str:
    return _mode


class CapacityExceeded(ValueError):
    def __init__(self, dimension: str, actual: int, limit: int, *, unit: str, phase: str):
        self.dimension, self.actual, self.limit, self.unit, self.phase = dimension, actual, limit, unit, phase
        self.mode = runtime_limit_mode()
        super().__init__(f'capacity_exceeded: {dimension} actual={actual} limit={limit} {unit} phase={phase}')

    def document(self) -> dict:
        return {'code': 'capacity_exceeded', 'dimension': self.dimension, 'actual': self.actual,
                'limit': self.limit, 'unit': self.unit, 'phase': self.phase, 'retryable': False,
                **({'mode': 'debug'} if self.mode == 'debug' else {})}


def check_capacity(limits: Mapping[str, int], dimension: str, actual: int, *, unit: str, phase: str) -> None:
    if actual > limits[dimension]:
        raise CapacityExceeded(dimension, actual, limits[dimension], unit=unit, phase=phase)


def observe_capacity(dimension: str, actual: int, *, phase: str | None = None,
                     unit: str = 'items', limits: Mapping[str, int] | None = None) -> bool:
    """Observe a soft boundary; debug interrupts before any recovery or omission."""
    selected = runtime_limits() if limits is None else limits
    exceeded = actual > selected[dimension]
    if exceeded and runtime_limit_mode() == 'debug':
        check_capacity(selected, dimension, actual, unit=unit, phase=phase or 'capacity')
    return exceeded
