"""Host-owned diagnostic records. Reported hypotheses never become Authority facts."""
from __future__ import annotations

from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
from threading import RLock
import time

from .native_research_bridge import read_json, write_json
from .general_pi_storage import sync_directory
from .application_capacity import limits

SCHEMA = 'capstone-systematic-diagnosis/1'
DIAGNOSIS_TOOLS = ('agent_diagnosis_record', 'agent_diagnosis_guide')
DIAGNOSIS_POLICY = {'schema': SCHEMA, 'max_probes': 6, 'max_seconds': 120}
# Internal correction defaults preserve the already-published policy and saved contexts.
DIAGNOSIS_MAX_CORRECTIONS = 3
DIAGNOSIS_MAX_SETTLE_REJECTIONS = 2
_BEGIN_FIELDS = {'issue', 'input_version', 'evidence_refs', 'hypothesis', 'minimal_probe',
                 'retry_reason', 'comparison', 'rejected_hypotheses', 'acceptance'}
_FINISH_FIELDS = {'probe_id', 'outcome', 'outcome_refs', 'information_gained', 'rejected_hypotheses', 'next_disposition'}
_REPORT_FIELDS = {'issue', 'outcome', 'information_gained', 'next_disposition'}
_REPORT_OPTIONAL = {'input_version', 'evidence_refs', 'hypothesis', 'minimal_probe', 'retry_reason',
                    'comparison', 'rejected_hypotheses', 'acceptance', 'outcome_refs', 'limitations', 'scope_ref'}


def _text(value, *, optional=False):
    if not isinstance(value, str) or len(value) > 2000 or (not optional and not value.strip()):
        raise ValueError('diagnosis text is invalid')
    return value


def _texts(value):
    if not isinstance(value, list) or len(value) > 16:
        raise ValueError('diagnosis references exceed bounds')
    return [_text(item) for item in value]


def _digest(value):
    def wire_value(item):
        if item is None:
            return ['null']
        if isinstance(item, bool):
            return ['bool', item]
        if isinstance(item, str):
            return ['str', item.encode('utf-8').hex()]
        if isinstance(item, (int, float)):
            number = float(item)
            if not math.isfinite(number):
                raise ValueError('diagnosis numbers must be finite')
            return ['num', struct.pack('>d', 0.0 if number == 0 else number).hex()]
        if isinstance(item, list):
            return ['array', [wire_value(element) for element in item]]
        if isinstance(item, dict) and all(isinstance(key, str) for key in item):
            return ['object', sorted([[key.encode('utf-8').hex(), wire_value(element)] for key, element in item.items()], key=lambda pair: pair[0])]
        raise ValueError('diagnosis values must be JSON data')
    return sha256(json.dumps(wire_value(value), separators=(',', ':'), allow_nan=False).encode('ascii')).hexdigest()


class NativeDiagnosis:
    def __init__(self, *, root, state_root, uid, policy, clock=time.time, storage=None):
        if policy != DIAGNOSIS_POLICY or uid == os.geteuid():
            raise ValueError('diagnosis requires a registered policy and separate host owner')
        self.root, self.state_root, self.uid = Path(root), Path(state_root), uid
        self.policy, self.clock, self.lock = dict(policy), clock, RLock()
        self.storage = storage
        for path, mode in ((self.root.parent, 0o711), (self.root, 0o750),
                           (self.root / 'responses', 0o750), (self.state_root, 0o700)):
            path.mkdir(parents=True, exist_ok=True)
            self._protect(path, mode)
        self.state_path = self.state_root / 'state.json'

    def _protect(self, path, mode):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid != os.geteuid():
            raise ValueError('diagnosis path owner is invalid')
        if os.geteuid() == 0:
            os.chown(path, 0, self.uid if mode in {0o750, 0o440} else 0)
        path.chmod(mode)

    def handle(self, frame):
        with self.lock:
            if (set(frame) != {'type', 'schema', 'request_id', 'operation', 'record'}
                    or frame['type'] != 'systematic_diagnosis_request' or frame['schema'] != SCHEMA
                    or not isinstance(frame['request_id'], str)
                    or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', frame['request_id'])
                    or len(json.dumps(frame, ensure_ascii=False, separators=(',', ':')).encode('utf-8')) > limits.rpc_frame_bytes):
                raise ValueError('diagnosis request is invalid')
            state = read_json(self.state_path, maximum=4 * 1024 * 1024) if self.state_path.exists() else {
                'schema': SCHEMA, 'policy': self.policy, 'scopes': {}, 'records': [], 'gaps': [], 'rejections': [], 'requests': {}}
            if state['policy'] != self.policy:
                raise ValueError('diagnosis policy identity changed')
            key = frame['request_id']
            digest = _digest(frame)
            prior = state['requests'].get(key)
            if prior:
                if prior['request_sha256'] != digest:
                    raise ValueError('diagnosis request identity changed')
                receipt = prior
            else:
                if len(state['requests']) >= 128:
                    raise ValueError('diagnosis receipt capacity exceeded')
                correction_scope = self._correction_scope(state, frame)
                corrections = state.setdefault('corrections', {})
                exhausted = corrections.get(correction_scope, 0) >= DIAGNOSIS_MAX_CORRECTIONS
                try:
                    if exhausted:
                        raise ValueError('diagnosis correction budget exhausted')
                    result = self._apply(state, frame)
                    receipt = dict(schema=SCHEMA, request_id=key, request_sha256=digest, ok=True, result=result)
                except (ValueError, KeyError, TypeError):
                    corrections[correction_scope] = corrections.get(correction_scope, 0) + (0 if exhausted else 1)
                    error = self._field_guidance(frame, correction_scope, corrections[correction_scope])
                    receipt = dict(schema=SCHEMA, request_id=key, request_sha256=digest, ok=False,
                                   code='diagnosis_record_invalid', error=error)
                # Commit the request and result together before publishing its receipt.
                state['requests'][key] = receipt
                if self.storage is None:
                    write_json(self.state_path, state, maximum=4 * 1024 * 1024)
                else:
                    # Use the existing host storage quota and atomic durable writer.
                    self.storage._write(self.state_path, json.dumps(state, ensure_ascii=False, allow_nan=False).encode())
                self._protect(self.state_path, 0o600)
                sync_directory(self.state_root)
            response = self.root / 'responses' / (key + '.json')
            write_json(response, receipt, maximum=524288)
            self._protect(response, 0o440)
            sync_directory(response.parent)
            return receipt

    def _apply(self, state, frame):
        operation, record = frame['operation'], frame['record']
        if not isinstance(record, dict):
            raise ValueError('diagnosis record is invalid')
        if operation == 'read' and set(record) <= {'scope_ref'}:
            scope_ref = record.get('scope_ref')
            records = [item for item in state['records'] if scope_ref is None or item['scope_ref'] == scope_ref]
            rejections = [item for item in state['rejections'] if scope_ref is None or item['scope_ref'] == scope_ref]
            return {'status': 'retained', 'policy': self.policy, 'records': records[-16:],
                    'records_truncated': len(records) > 16, 'rejections': rejections[-16:], 'gaps': state['gaps'][-16:],
                    'scopes': [self._scope_status(state, ref) for ref in state['scopes']],
                    'remaining_probes': self.policy['max_probes'] if scope_ref is None else self._scope_status(state, scope_ref)['remaining_probes']}
        if operation == 'check_scope':
            if set(record) != {'scope_ref'}:
                raise ValueError('diagnosis scope fields are invalid')
            return self._scope_status(state, record['scope_ref'])
        if operation == 'report':
            if (not _REPORT_FIELDS <= set(record) or set(record) - _REPORT_FIELDS - _REPORT_OPTIONAL
                    or record['outcome'] not in {'passed', 'failed', 'not_run', 'unknown'}
                    or record['next_disposition'] not in {'continue', 'change_method', 'retain_gap', 'stop_dependent', 'request_input'}):
                raise ValueError('diagnosis report fields are invalid')
            checked = {name: _texts(value) if name in {'evidence_refs', 'outcome_refs', 'limitations', 'rejected_hypotheses'}
                else _text(value, optional=name in {'hypothesis', 'minimal_probe', 'comparison'}) for name, value in record.items()}
            if checked.get('acceptance', 'advisory') not in {'advisory', 'objective'}:
                raise ValueError('diagnosis acceptance is invalid')
            if len(state['records']) >= 64:
                raise ValueError('diagnosis record capacity exceeded')
            scope_ref = checked.get('scope_ref', 'unbound-task')
            if not isinstance(scope_ref, str) or scope_ref != 'unbound-task' and scope_ref not in state['scopes']:
                raise ValueError('diagnosis scope is not observed')
            self._scope(state, scope_ref)
            saved = {'acceptance': 'advisory', **checked, 'scope_ref': scope_ref,
                     'report_id': 'diagnosis-report:' + frame['request_id'], 'probe_state': 'reported',
                     'reported_only': True, 'recorded_at': self.clock()}
            state['records'].append(saved)
            return {'status': 'recorded', 'record': saved, 'acceptance_unchanged': True}
        if operation == 'observe_rejection':
            if set(record) != {'tool_call_id', 'selection', 'code', 'duration_ms'}:
                raise ValueError('diagnosis rejection fields are invalid')
            selection = record['selection']
            if (not isinstance(selection, dict) or set(selection) != {'tool_name', 'input', 'action_identity'}
                    or not isinstance(selection['input'], dict)
                    or type(record['duration_ms']) not in {int, float} or not 0 <= record['duration_ms'] <= 86400000):
                raise ValueError('diagnosis selection is invalid')
            _text(selection['tool_name'])
            _text(record['tool_call_id'])
            code = _text(record['code'])
            selection_key = _digest(selection)
            scope_ref = 'scope-' + _digest({'selection_key': selection_key, 'code': code})
            scope = self._scope(state, scope_ref, selection_key=selection_key)
            if scope['used'] < self.policy['max_probes']:
                scope['used'] += 1
                scope['elapsed_seconds'] += record['duration_ms'] / 1000
                state['rejections'].append({'tool_call_id': record['tool_call_id'], 'tool_name': selection['tool_name'],
                    'code': code, 'scope_ref': scope_ref, 'observed_at': self.clock(), 'reported_only': True})
            return self._scope_status(state, scope_ref)
        if operation == 'begin':
            required = _BEGIN_FIELDS
            if not required <= set(record) or set(record) - required - {'scope_ref'} or record['acceptance'] not in {'advisory', 'objective'}:
                raise ValueError('diagnosis fields are invalid')
            checked = {name: _texts(value) if name in {'evidence_refs', 'rejected_hypotheses'} else
                       _text(value, optional=name in {'hypothesis', 'minimal_probe', 'comparison'})
                       for name, value in record.items()}
            gap = {'status': 'gap', 'next_disposition': 'retain_gap', 'retained_records': len(state['records']),
                   'acceptance_unchanged': True}
            # Missing optional research proof records a gap; it does not reject delivery.
            hypothesis, minimal_probe = checked['hypothesis'], checked['minimal_probe']
            if not isinstance(hypothesis, str) or not isinstance(minimal_probe, str):
                raise ValueError('diagnosis hypothesis and probe must be text')
            if not hypothesis.strip() or not minimal_probe.strip():
                if len(state['gaps']) < self.policy['max_probes']:
                    state['gaps'].append({**checked, 'reported_only': True, 'next_disposition': 'retain_gap'})
                return {**gap, 'reason': 'Specify a hypothesis and minimal probe to reserve diagnostic work.'}
            now = self.clock()
            # Model issue/input labels cannot mint fresh budgets. Only an observed
            # host selection creates an independent scope; other probes share fallback.
            scope_ref = checked.get('scope_ref') or 'unbound-task'
            if checked.get('scope_ref') and scope_ref not in state['scopes']:
                raise ValueError('diagnosis scope is not observed')
            scope = self._scope(state, scope_ref)
            status = self._scope_status(state, scope_ref)
            if status['status'] == 'exhausted':
                return {**gap, **status}
            scope['used'] += 1
            saved = {**checked, 'probe_id': frame['request_id'], 'outcome': 'unknown', 'probe_state': 'reserved',
                     'scope_ref': scope_ref, 'reported_only': True, 'reserved_at': now, 'next_disposition': 'probe'}
            state['records'].append(saved)
            return {'status': 'probe_reserved', 'record': saved,
                    'remaining_probes': self.policy['max_probes'] - scope['used']}
        if operation == 'finish':
            if (set(record) != _FINISH_FIELDS
                    or record['outcome'] not in {'passed', 'failed', 'not_run', 'unknown'}
                    or record['next_disposition'] not in {'continue', 'change_method', 'retain_gap', 'stop_dependent', 'request_input'}):
                raise ValueError('diagnosis outcome is invalid')
            saved = next((item for item in state['records'] if item.get('probe_id') == record['probe_id']), None)
            if saved is None:
                raise ValueError('diagnosis probe is unavailable')
            if saved.get('finished_at') is not None:
                raise ValueError('diagnosis outcome is already retained')
            outcome = {**record, 'outcome_refs': _texts(record['outcome_refs']),
                       'information_gained': _text(record['information_gained']),
                       'rejected_hypotheses': _texts(record['rejected_hypotheses'])}
            finished = self.clock()
            state['scopes'][saved['scope_ref']]['elapsed_seconds'] += max(0, finished - saved['reserved_at'])
            saved.update(outcome, finished_at=finished, probe_state='finished')
            return {'status': 'recorded', 'record': saved, 'acceptance_unchanged': True}
        raise ValueError('diagnosis operation is invalid')

    def _correction_scope(self, state, frame):
        record = frame['record'] if isinstance(frame['record'], dict) else {}
        operation = frame['operation']
        target = 'unbound-task'
        if operation == 'finish':
            candidate = record.get('probe_id')
            target = candidate if isinstance(candidate, str) and any(
                item.get('probe_id') == candidate for item in state['records']) else 'unresolved-probe'
        elif isinstance(record.get('scope_ref'), str) and record['scope_ref'] in state['scopes']:
            target = record['scope_ref']
        return 'correction-' + _digest({'operation': operation, 'host_target': target})

    def _field_guidance(self, frame, scope, used):
        operation = frame['operation']
        required, optional = {'begin': (_BEGIN_FIELDS, {'scope_ref'}), 'finish': (_FINISH_FIELDS, set()),
            'report': (_REPORT_FIELDS, _REPORT_OPTIONAL), 'read': (set(), {'scope_ref'})}.get(operation, (set(), set()))
        record = frame['record'] if isinstance(frame['record'], dict) else {}
        exhausted = used >= DIAGNOSIS_MAX_CORRECTIONS
        return {'category': 'rejected', 'status': 'exhausted' if exhausted else 'rejected',
                'correction_scope': scope, 'remaining_corrections': max(0, DIAGNOSIS_MAX_CORRECTIONS - used),
                'max_settle_rejections': DIAGNOSIS_MAX_SETTLE_REJECTIONS,
                'operation': operation, 'required_fields': sorted(required),
                'missing_fields': sorted(required - set(record)),
                'extra_fields': [key if re.fullmatch(r'[A-Za-z_]{1,64}', key) else '<unexpected field>'
                                 for key in sorted(set(record) - required - optional)],
                'next_disposition': 'retain_gap' if exhausted else 'correct_fields',
                'message': ('This operation/probe correction budget is exhausted. Keep useful work and the metadata gap; '
                    'use report for a separate honest observation or continue independent work. Do not repeat this rejected operation.' if exhausted else
                    'Known field rejection; no outcome was changed. Use only the listed fields. outcome is passed/failed/not_run/unknown; '
                    'next_disposition is continue/change_method/retain_gap/stop_dependent/request_input. '
                    'For ordinary work prefer report: issue, outcome, information_gained, next_disposition; no probe ID is needed.')}

    def _scope(self, state, scope_ref, *, selection_key=None):
        if scope_ref not in state['scopes']:
            if len(state['scopes']) >= 32:
                raise ValueError('diagnosis scope capacity exceeded')
            state['scopes'][scope_ref] = {'used': 0, 'elapsed_seconds': 0, 'selection_key': selection_key}
        return state['scopes'][scope_ref]

    def _scope_status(self, state, scope_ref):
        scope = state['scopes'][scope_ref]
        elapsed = scope['elapsed_seconds'] + sum(max(0, self.clock() - item['reserved_at'])
            for item in state['records'] if item['scope_ref'] == scope_ref and item['probe_state'] == 'reserved')
        exhausted = scope['used'] >= self.policy['max_probes'] or elapsed >= self.policy['max_seconds']
        return {'scope_ref': scope_ref, 'selection_key': scope['selection_key'],
                'status': 'exhausted' if exhausted else 'investigating',
                'next_disposition': 'retain_gap' if exhausted else 'change_method',
                'remaining_probes': max(0, self.policy['max_probes'] - scope['used']), 'elapsed_seconds': elapsed,
                'reason': 'This selection is exhausted. Keep useful work, deliver its gap, or continue a different permitted action.' if exhausted else
                    'Inspect the evidence and correct or justify this selection. Read agent_diagnosis_guide; recover unknown effects before repeating them.'}
