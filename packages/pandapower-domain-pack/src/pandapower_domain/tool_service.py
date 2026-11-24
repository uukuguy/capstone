"""Pack-owned published tool execution with an application-selected workspace."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from capability_agent.runtime.execution_queue import ExecutionReceiptError
from pandapower_domain.authority import ContentReferenceVerifier, PandapowerArtifactAuthority, SimulatorIntegrityError

from pandapower_domain.execution import (GridctlExecutor, SimulatorCapabilityError,
    source_execution_queue, execution_receipt_writer)
from pandapower_domain.profile import build_pandapower_profile
from pandapower_domain.provisioning import PandapowerRuntimeProvisioner


_TASK_ID = re.compile(r'^[A-Za-z0-9_-]{1,80}$')
_REF = re.compile(r'^(?:result|evidence|context|revision):sha256:[0-9a-f]{64}$')
_FIELD = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,63}$')
_DATASET = re.compile(r'^result\.res_[a-z0-9_]+$')
_QUERY_DELIVERY = 'capstone-query-delivery/1'


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _delivery_cell(value) -> bool:
    if value is None or isinstance(value, (str, bool)):
        return not isinstance(value, str) or ('\n' not in value and '\r' not in value)
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _argument_references(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _argument_references(item)
    elif isinstance(value, list):
        for item in value:
            yield from _argument_references(item)
    elif isinstance(value, str) and re.fullmatch(r'(?:result|evidence|context|revision):sha256:[0-9a-f]{64}', value):
        yield value


class PandapowerToolService:
    """Serve the installed pandapower profile's published tools."""

    def __init__(self, *, workspace_root: Path | None = None) -> None:
        configured = os.environ.get('CAPSTONE_DOMAIN_TOOL_WORKSPACE')
        self._root = Path(workspace_root or configured or (Path(os.environ.get('CAPSTONE_RUNS_ROOT', '/tmp')) / 'domain-tools'))
        self._receipt_root = Path(os.environ.get('CAPSTONE_DOMAIN_EXECUTION_RECEIPTS_ROOT') or self._root)
        self._lock = Lock()
        self._profile = None
        self._capabilities: dict[str, str] = {}
        self._executors: dict[str, GridctlExecutor] = {}
        self._read_only: dict[str, bool] = {}
        self._queue = source_execution_queue()

    def _installed(self):
        if self._profile is None:
            self._profile = build_pandapower_profile()
        return self._profile

    def catalog(self, profile_id: str, profile_version: str) -> dict:
        profile = self._installed()
        manifest = profile.manifest
        if profile_id != manifest.domain_id or profile_version != manifest.version:
            raise KeyError('domain pack is not published by this worker')
        tools, hashes, capabilities, read_only = {}, {}, {}, {}
        for document in profile.contract_source.load():
            if document.get('availability') != 'published':
                continue
            name = document.get('tool_name')
            capability = document.get('id')
            schema = document.get('input_schema')
            if not isinstance(name, str) or not isinstance(capability, str) or not isinstance(schema, dict):
                continue
            describe = profile.tool_description_builder
            if describe is None:
                raise ValueError('published domain tool description builder is unavailable')
            description = describe(document)
            body = {'description': description, 'inputSchema': schema, 'capability': capability}
            tools[name] = {'description': description, 'inputSchema': schema}
            hashes[name] = hashlib.sha256(_canonical(body).encode()).hexdigest()
            capabilities[name] = capability
            read_only[name] = document.get('state_effect') == 'none'
        if not tools:
            raise KeyError('domain pack is not published by this worker')
        with self._lock:
            self._capabilities = capabilities
            self._read_only = read_only
        return {
            'schema': 'capstone-domain-tool-catalog/1',
            'profile_id': manifest.domain_id,
            'profile_version': manifest.version,
            'implementation_family': 'pandapower',
            'tools': tools,
            'tool_hashes': hashes,
        }

    def result_read_guidance(self) -> str | None:
        readers = {cap: name for name, cap in self._capabilities.items()}
        listing, query = readers.get('result.dataset.list'), readers.get('result.dataset.query')
        if not listing or not query:
            return None
        describe = readers.get('result.dataset.describe')
        return (
            f'To read saved result rows, load {listing} and {query}'
            + (f' and {describe}' if describe else '')
            + '. Use the returned result_ref with the list tool. '
            + (f'Use {describe} to confirm fields and units. ' if describe else '')
            + f'Use {query} to select, sort and limit rows from the same result. '
              'Keep the producing evidence_refs for claims. This result_ref is an Authority reference.'
        )

    def model_result(self, capability: str, result: dict) -> dict | None:
        if capability == 'context.open':
            overview = result.get('overview')
            reader = next((name for name, cap in self._capabilities.items() if cap == 'context.get'), None)
            if not reader or not isinstance(overview, list) or not isinstance(result.get('context_ref'), str):
                return None
            return {**{key: value for key, value in result.items() if key != 'overview'},
                    'overview_dataset_count': len(overview),
                    'overview_read': {'tool': reader, 'arguments': {
                        'context_ref': result['context_ref'], 'include_overview': True}}}
        if capability not in {'analysis.powerflow.ac.run', 'result.dataset.list'}:
            return None
        datasets = result.get('datasets')
        if not isinstance(datasets, list) or any(
            not isinstance(item, dict) or not isinstance(item.get('dataset'), str)
            or type(item.get('row_count')) is not int or item['row_count'] < 0
            for item in datasets
        ):
            return None
        populated = [{'dataset': item['dataset'], 'row_count': item['row_count']}
                     for item in datasets if item['row_count']]
        view = {key: value for key, value in result.items() if key != 'datasets'}
        if capability == 'analysis.powerflow.ac.run':
            return {**view, 'dataset_count': len(datasets), 'nonempty_dataset_count': len(populated)}
        return {**view, 'datasets': populated, 'field_metadata': 'Use the published dataset describe tool for fields and units.',
                'empty_datasets': [item['dataset'] for item in datasets if item['row_count'] == 0]}

    def model_guidance(self, capability: str, result: dict) -> str | None:
        readers = {cap: name for name, cap in self._capabilities.items()}
        if capability == 'context.open' and (solver := readers.get('analysis.powerflow.ac.run')):
            args = _canonical({'context_ref': result['context_ref']})
            return (f'For a baseline AC power flow, call {solver} with {args}; '
                    'omit solver overrides unless requested or justified. The solver applies the registered defaults.')
        if capability == 'analysis.powerflow.ac.run' and (query := readers.get('result.dataset.query')):
            dataset = next((row for row in result.get('datasets', [])
                            if row['dataset'] == 'result.res_bus' and row['row_count'] > 0
                            and {'index', 'vm_pu'}.issubset(row['available_fields'])), None)
            if dataset:
                args = _canonical({'result_ref': result['result_ref'], 'dataset': dataset['dataset'],
                                   'select': ['index', 'vm_pu'],
                                   'sort': {'field': 'vm_pu', 'direction': 'ascending'}})
                other_read = self.result_read_guidance()
                return (f'For lowest bus voltage, call {query} with {args}. '
                        'Set limit to the requested count. '
                        'The query delivery keeps returned order, column units and evidence_refs. '
                        'Use that delivery as the answer table. '
                        + (f'For other datasets: {other_read}' if other_read else ''))
        return None

    def query_delivery(self, result: dict, arguments: dict, authority, evidence_refs: list) -> dict | None:
        """Project one admitted query as rows, stored units and evidence.

        A missing unit catalog does not invent units or reject the rows.
        """
        select = arguments.get('select')
        rows = result.get('rows')
        result_ref = result.get('result_ref')
        dataset = result.get('dataset')
        if (not isinstance(select, list) or not 1 <= len(select) <= 32
                or any(not isinstance(name, str) or not _FIELD.fullmatch(name) for name in select)
                or len(set(select)) != len(select)
                or not isinstance(rows, list) or len(rows) > 100
                or not isinstance(result_ref, str) or not _REF.fullmatch(result_ref)
                or not isinstance(dataset, str) or not _DATASET.fullmatch(dataset)
                or not isinstance(evidence_refs, list) or len(evidence_refs) > 16
                or any(not isinstance(item, str) or not _REF.fullmatch(item) for item in evidence_refs)):
            return None
        if any(not isinstance(row, dict) or any(key not in select for key in row) for row in rows):
            return None
        counts = {}
        for key in ('row_count', 'returned_row_count', 'offset'):
            value = result.get(key)
            if type(value) is not int or value < 0:
                return None
            counts[key] = value
        next_offset = result.get('next_offset')
        if (counts['returned_row_count'] != len(rows) or counts['row_count'] < len(rows)
                or (next_offset is not None and type(next_offset) is not int)):
            return None
        projected = [{name: row.get(name) for name in select} for row in rows]
        if any(not _delivery_cell(value) for row in projected for value in row.values()):
            return None
        units = self._dataset_units(authority, result_ref, dataset, select)
        return {'schema': _QUERY_DELIVERY, 'result_ref': result_ref, 'dataset': dataset,
                'columns': [{'name': name, **({'unit': units[name]} if name in units else {})} for name in select],
                'rows': projected, **counts, 'next_offset': next_offset,
                'evidence_refs': list(evidence_refs)}

    def _dataset_units(self, authority, result_ref: str, dataset: str, names: list[str]) -> dict[str, str]:
        try:
            fields = authority.verify_result(result_ref).document['datasets'][dataset]['fields']
        except Exception:
            return {}
        if not isinstance(fields, list):
            return {}
        units = {}
        for field in fields:
            if not isinstance(field, dict):
                continue
            name, unit = field.get('name'), field.get('unit')
            if isinstance(name, str) and name in names and isinstance(unit, str) and unit.strip():
                units[name] = unit
        return units

    def invoke(self, document: dict, *, workspace_id: str, authority_inputs=()) -> dict:
        if not isinstance(workspace_id, str) or not _TASK_ID.fullmatch(workspace_id):
            raise ValueError('domain workspace identity is invalid')
        task_id = document.get('task_id')
        name = document.get('name')
        arguments = document.get('arguments')
        if (not isinstance(task_id, str) or not _TASK_ID.fullmatch(task_id)
                or not isinstance(name, str) or not isinstance(arguments, dict)):
            raise ValueError('domain tool call is invalid')
        if not self._capabilities:
            manifest = self._installed().manifest
            self.catalog(manifest.domain_id, manifest.version)
        capability = self._capabilities.get(name)
        if capability is None:
            raise KeyError('domain tool is not published')
        call_id = document.get('call_id')
        if not isinstance(call_id, str) or not call_id or len(call_id) > 256:
            raise ValueError('domain tool call identity is invalid')
        receipt = self._queue.receipt(task_id=task_id, call_id=call_id,
            observer=self._receipt_writer(task_id))
        read_only = self._read_only.get(name, False)
        refs = set(_argument_references(arguments))
        owned_inputs = [item for item in authority_inputs if item['authority_id'] == PandapowerArtifactAuthority.authority_id]
        referenced = {ref for ref in refs if not ref.startswith('revision:')}
        revisions = refs - referenced

        def shared_refs(item):
            return set((*item['result_refs'], *item['evidence_refs'], *item.get('context_refs', ())))

        linked = [item for item in owned_inputs if referenced & shared_refs(item)
                  and (item['owner'] != workspace_id or referenced.intersection(
                      (*item['result_refs'], *item['evidence_refs'])))]
        delegated = next((item for item in linked if referenced <= shared_refs(item)), None)
        with ExitStack() as opened:
            execution_id = workspace_id
            if delegated is not None and read_only:
                folder = Path(opened.enter_context(TemporaryDirectory(prefix='grant-', dir=self._root)))
                execution_id = folder.name
            resource = str((self._root / execution_id).resolve())
            lease = opened.enter_context(self._queue.acquire(receipt, resource=resource, read_only=read_only))
            try:
                if linked and (delegated is None or not read_only):
                    raise ValueError('delegated authority input requires a granted read-only tool call')
                if delegated is not None:
                    if not _TASK_ID.fullmatch(delegated['owner']):
                        raise ValueError('delegated authority owner is invalid')
                    owner = PandapowerArtifactAuthority(self._root / delegated['owner'])
                    owner.stage_read_inputs(self._root / execution_id, delegated['result_refs'], delegated['evidence_refs'],
                                            delegated.get('context_refs', ()), revisions)
                result = self._executor(execution_id).invoke(capability, arguments,
                    execution_lease=lease,
                    execution_observer=lambda phase: self._queue.record(receipt, phase, provenance='authority_process'))
                response = ({'ok': True, 'result': result} if isinstance(result, dict)
                    else {'ok': False, 'error': {'message': 'domain tool call failed'}})
                if isinstance(result, dict):
                    authority = PandapowerArtifactAuthority(self._root / execution_id)
                    verified = authority.admit(capability, result, ())
                    evidence = {item.reference: item for item in verified.evidence}
                    result_refs = {item.reference for item in verified.results}
                    context_ref = result.get('context_ref')
                    # Forward only a context the Pack opened or the call used.
                    context_refs = [item.reference for item in verified.context
                                    if item.reference == context_ref
                                    and (capability == 'context.open' or item.reference in referenced)
                                    and (delegated is None or item.reference in delegated.get('context_refs', ()))]
                    if context_refs and 'revision_ref' in result and any(
                            item.reference == context_ref and item.document['revision_ref'] != result['revision_ref']
                            for item in verified.context):
                        raise SimulatorIntegrityError('tool response does not match the verified context revision')
                    if delegated is not None and (not result_refs.issubset(delegated['result_refs'])
                            or not evidence.keys() <= set(delegated['evidence_refs'])):
                        raise ValueError('delegated authority response exceeds the grant')
                    if result_refs and not evidence:
                        prior_evidence = (delegated['evidence_refs'] if delegated is not None else
                            document.get('management', {}).get('prior_evidence_refs', ()))
                        for ref in prior_evidence:
                            try:
                                item = authority.verify_evidence(ref)
                            except SimulatorIntegrityError:
                                # A different Pack or workspace can own a historical handle.
                                continue
                            if (item.document.get('result_ref') in result_refs
                                    and item.document.get('context_ref') == result.get('context_ref')
                                    and item.document.get('revision_ref') == result.get('revision_ref')):
                                evidence[ref] = item
                    if result_refs or evidence or context_refs:
                        response['authority_references'] = {
                            'authority_id': authority.authority_id,
                            'capability_id': capability,
                            'result_refs': [item.reference for item in verified.results],
                            'evidence_refs': list(evidence),
                            **({'context_refs': context_refs} if context_refs else {}),
                        }
                        if capability == 'result.branches.rank' and result_refs:
                            selected = [row['branch_ref'] for row in result['branches'][:20]]
                        elif capability == 'result.dataset.query' and result_refs:
                            from .network_annotations import selected_loading_assets
                            selected = selected_loading_assets(arguments, verified.results[0].document)
                        else:
                            selected = []
                        if selected:
                            response['authority_references']['view_refs'] = selected
                        guidance = self.model_guidance(capability, result)
                        if result_refs and not read_only and guidance is None:
                            guidance = self.result_read_guidance()
                        if guidance:
                            response['model_guidance'] = guidance
                        if (result_refs or context_refs) and (view := self.model_result(capability, result)) is not None:
                            response['model_result'] = view
                        if capability == 'result.dataset.query' and (delivery := self.query_delivery(
                                result, arguments, authority, list(evidence))) is not None:
                            response['query_delivery'] = delivery
                            response['model_result'] = delivery
                            response['model_guidance'] = (
                                'These rows are the answer table in returned order. '
                                'Use the column units and evidence_refs. Do not retype the rows.')
            except ExecutionReceiptError:
                raise
            except SimulatorCapabilityError as error:
                response = {'ok': False, 'error': error.error if isinstance(error.error, dict) else {'message': 'domain tool call failed'}}
            except Exception:
                response = {'ok': False, 'error': {'message': 'domain tool call failed'}}
        return {**response, 'execution_receipt': receipt}

    def recover(self, receipt):
        """Admit a saved task scope only after finding its exact owner receipt."""
        task_id = receipt.get('task_id')
        if not isinstance(task_id, str) or not re.fullmatch(r'pi-[a-f0-9]{64}', task_id):
            raise ValueError('legacy task identity is invalid')
        ledger = ContentReferenceVerifier(self._receipt_root / task_id)
        directory = ('execution-receipts',)
        try:
            files = ledger._list_directory(directory)
            if len(files) > 256:
                raise ValueError('legacy receipt directory exceeds bounds')
            for name in files:
                if not re.fullmatch(r'[a-f0-9]{32}\.json', name):
                    continue
                saved = ledger._try_json_document((*directory, name), 'legacy execution receipt')
                if saved is not None and saved[1] == receipt:
                    return PandapowerArtifactAuthority(self._root / task_id).recover_references()
        except SimulatorIntegrityError:
            raise ValueError('legacy authority content is unavailable') from None
        raise ValueError('legacy execution receipt does not match its owner')

    def _receipt_writer(self, task_id):
        # Each invocation gets a private control record, independent of HTTP
        # delivery. This is host telemetry, never an Authority result/evidence.
        return execution_receipt_writer(self._receipt_root, task_id)

    def _executor(self, task_id: str) -> GridctlExecutor:
        with self._lock:
            cached = self._executors.get(task_id)
            if cached is not None:
                return cached
            if len(self._executors) >= 64:
                self._executors.pop(next(iter(self._executors)))
            workspace = self._root / task_id
            workspace.mkdir(parents=True, exist_ok=True)
            root = Path(__file__).resolve().parents[4]
            executable = PandapowerRuntimeProvisioner(repository_root=root)._resolve_executable()
            executor = GridctlExecutor(executable=executable, workspace=workspace, timeout_seconds=180)
            self._executors[task_id] = executor
            return executor
