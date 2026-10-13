"""Application-owned, attempt-scoped preparation of verified table delivery."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from hashlib import sha256
import json
from pathlib import Path
import re

from capability_agent._safe_files import ensure_bound_directory, read_bound_regular_path, write_bound_text
from .harness import normalize_runtime_event

_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')
ProjectionBuilder = Callable[[tuple[str, ...], tuple[str, ...], tuple[Mapping[str, object], ...]],
                             tuple[Mapping[str, object], ...]]


class ResultDeliveryChannel:
    """A presentation receipt is not new evidence or a completed answer."""

    def __init__(self, root: Path, *, thread_id: str, attempt_id: str, binding_ids: set[str],
                 verify: Callable[..., None], project: ProjectionBuilder,
                 is_active: Callable[[], bool] = lambda: False) -> None:
        if not _ID.fullmatch(thread_id) or not _ID.fullmatch(attempt_id):
            raise ValueError('invalid result delivery identity')
        self.root = ensure_bound_directory(root)
        ensure_bound_directory(self.root / 'requests')
        ensure_bound_directory(self.root / 'receipts')
        self.thread_id, self.attempt_id = thread_id, attempt_id
        self._binding_ids, self._verify, self._project = binding_ids, verify, project
        self._is_active = is_active
        self._events: list[Mapping[str, object]] = []
        self._results: set[str] = set()
        self._evidence: set[str] = set()
        self._cache: dict[tuple[tuple[str, ...], tuple[str, ...]], tuple[Mapping[str, object], ...]] = {}
        self._write(self.root / 'binding.json', {'schema': 'capstone-result-delivery/1',
            'thread_id': thread_id, 'attempt_id': attempt_id})

    def bind_active_check(self, check: Callable[[], bool]) -> None:
        self._is_active = check

    def observe(self, event: Mapping[str, object]) -> None:
        normalized = normalize_runtime_event(event, runtime_mode='capstone')
        if normalized is None or normalized['event_type'] != 'tool_completed':
            return
        payload = normalized['payload']
        if not isinstance(payload, Mapping) or payload.get('binding_id') not in self._binding_ids:
            return
        event = payload
        self._events.append(dict(event))
        if event.get('ok') is not True:
            return
        for field, target in (('result_refs', self._results), ('evidence_refs', self._evidence)):
            refs = event.get(field)
            if isinstance(refs, (list, tuple)):
                target.update(ref for ref in refs if isinstance(ref, str))

    def projections(self, results: tuple[str, ...], evidence: tuple[str, ...],
                    events: tuple[Mapping[str, object], ...]) -> tuple[Mapping[str, object], ...]:
        """Reuse immutable projections only; final admission still verifies artifacts."""
        key = (tuple(sorted(set(results))), tuple(sorted(set(evidence))))
        if key not in self._cache:
            self._cache = {key: self._project(results, evidence, events)}
        return self._cache[key]

    def prepare(self, result_ref: str) -> dict[str, object]:
        if not self._is_active():
            return {'status': 'unavailable', 'code': 'attempt_closed'}
        if result_ref not in self._results:
            return {'status': 'unavailable', 'code': 'result_not_observed'}
        results, evidence, events = tuple(sorted(self._results)), tuple(sorted(self._evidence)), tuple(self._events)
        try:
            self._verify(results, evidence, events)
            projections = self.projections(results, evidence, events)
            if not self._is_active():
                return {'status': 'unavailable', 'code': 'attempt_closed'}
            selected = [p for p in projections if p.get('result_ref') == result_ref]
            if not selected:
                return {'status': 'unavailable', 'code': 'result_projection_unavailable'}
            # Persist all values before returning a metadata-only receipt. The
            # normal final answer admission publishes the same typed projections.
            payload = json.dumps(projections, ensure_ascii=False, sort_keys=True)
            digest = sha256(payload.encode()).hexdigest()
            self._write(self.root / f'projection-{digest}.json', projections)
            tables = []
            summary = []
            for projection in selected:
                raw_tables = projection.get('tables', [])
                raw_summary = projection.get('summary', [])
                if not isinstance(raw_tables, (list, tuple)) or not isinstance(raw_summary, (list, tuple)):
                    raise ValueError('invalid result presentation')
                summary.extend(raw_summary)
                for table in raw_tables:
                    if not isinstance(table, Mapping) or not isinstance(table.get('rows'), (list, tuple)):
                        raise ValueError('invalid result table')
                    pagination = table.get('pagination')
                    tables.append({'table_id': table['table_id'], 'title': table['title'],
                        'columns': table['columns'],
                        'total_rows': pagination['total_rows'] if isinstance(pagination, Mapping) else len(table['rows']),
                        'complete': projection.get('status') == 'completed' and not pagination})
            return {'status': 'prepared', 'result_ref': result_ref,
                'projection_sha256': digest, 'answer_admission_pending': True,
                'projection_status': [p['status'] for p in selected], 'tables': tables,
                'summary': summary,
                'limitations': [p.get('unavailable_reason') for p in selected if p.get('unavailable_reason')]}
        except Exception:
            # Keep the original tool results and let the agent use the existing
            # published read tools. A presentation failure must not stop research.
            return {'status': 'unavailable', 'code': 'result_delivery_not_verified',
                    'message': 'Table delivery could not be prepared. Existing results remain available through published tools.'}

    def drain(self) -> None:
        handled = 0
        for path in sorted((self.root / 'requests').glob('*.json')):
            if not _ID.fullmatch(path.stem) or path.lstat().st_size > 8192:
                raise ValueError('invalid result delivery request')
            raw = read_bound_regular_path(path)
            digest = sha256(raw).hexdigest()
            receipt_path = self.root / 'receipts' / path.name
            if receipt_path.exists() or receipt_path.is_symlink():
                receipt = json.loads(read_bound_regular_path(receipt_path))
                if receipt.get('request_sha256') != digest:
                    raise ValueError('result delivery request changed after receipt')
                continue
            try:
                request = json.loads(raw)
                if (set(request) != {'request_id', 'thread_id', 'attempt_id', 'result_ref'}
                    or request['request_id'] != path.stem or request['thread_id'] != self.thread_id
                    or request['attempt_id'] != self.attempt_id
                    or not isinstance(request['result_ref'], str)):
                    raise ValueError('invalid delivery binding')
                receipt = self.prepare(request['result_ref'])
            except (ValueError, TypeError, KeyError):
                receipt = {'status': 'unavailable', 'code': 'invalid_result_delivery_request'}
            self._write(receipt_path, {**receipt, 'schema': 'capstone-result-delivery-receipt/1',
                'thread_id': self.thread_id, 'attempt_id': self.attempt_id,
                'request_id': path.stem, 'request_sha256': digest})
            handled += 1
            if handled == 16:
                break

    @staticmethod
    def _write(path: Path, value: object) -> None:
        write_bound_text(path, json.dumps(value, ensure_ascii=False, sort_keys=True) + '\n')
