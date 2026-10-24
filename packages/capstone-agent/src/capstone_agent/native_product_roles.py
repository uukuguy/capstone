"""Optional presentation declarations; never certify completion or evidence."""
import json
import os
from pathlib import Path, PurePosixPath
import stat
from hashlib import sha256

ROLES = ('primary', 'support', 'reproduction')
_PATH_POLICY = json.loads((Path(__file__).parent / 'resources/product-path-policy.json').read_text())


def publishable_product_path(path):
    parts = PurePosixPath(path).parts
    return bool(parts) and not (
        any((_PATH_POLICY['exclude_hidden_parts'] and part.startswith('.'))
            or part in _PATH_POLICY['excluded_parts'] for part in parts)
        or PurePosixPath(path).suffix.lower() in _PATH_POLICY['excluded_suffixes']
        or parts[0] in _PATH_POLICY['excluded_roots'])


def read_product_roles(workspace):
    """Ignore invalid hints. Collection still verifies each actual file."""
    try:
        fd = os.open(workspace / '.capstone-products.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > 65536:
                return {}
            document = json.loads(source.read(65537))
        if (not isinstance(document, dict) or document.get('schema') != 'capstone-workspace-products/1'
                or not isinstance(document.get('products'), list) or len(document['products']) > 128):
            return {}
    except (OSError, ValueError):
        return {}
    roles = {}
    for item in document['products']:
        if not isinstance(item, dict):
            continue
        path, role = item.get('path'), item.get('role')
        if (not isinstance(path, str) or not path or len(path.encode()) > 1024
                or role not in ROLES or '\\' in path or any(ord(c) < 32 for c in path)
                or PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts
                or str(PurePosixPath(path)) != path):
            continue
        roles[path] = role
    return roles


def file_artifact_id(path, digest):
    return 'file-' + sha256(path.encode()).hexdigest()[:16] + '-' + digest


def delivery_presentation(view, *, task_id, attempt_id, owner):
    """Derive presentation only from an exact committed terminal checkpoint."""
    from .native_research_bridge import _committed_cycle_checkpoint
    prefix = 'runtime.checkpoint.' + sha256(task_id.encode()).hexdigest()[:20] + '.'
    notes = (view.get('state') or {}).get('notes', [])
    for note in reversed(notes):
        if not note.get('note_id', '').startswith(prefix):
            continue
        saved = _committed_cycle_checkpoint({'ref': note['note_id'], 'revision': view['research_revision']},
            owner=owner, task_id=task_id, attempt_id=attempt_id, view=view)
        state = saved['snapshot']
        if state.get('phase') not in {'done', 'limited'} or state.get('pending_action') is not None:
            return None
        if saved.get('status') != state['phase'] or not isinstance(state.get('delivery_products'), list):
            return None
        core = {path for objective in state.get('objectives', []) for path in objective.get('product_paths', [])}
        products = []
        for selected in state['delivery_products']:
            path, ref = selected.get('path'), selected.get('ref')
            product = next((p for p in saved.get('products', []) if p.get('path') == path and p.get('ref') == ref), None)
            if (product is None or product.get('status') != 'ready' or product.get('attempt_id') != attempt_id
                    or not isinstance(path, str) or not publishable_product_path(path)
                    or '\\' in path or PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts
                    or str(PurePosixPath(path)) != path):
                continue
            digest, size = product.get('sha256'), product.get('bytes')
            if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest) or type(size) is not int or size < 1:
                continue
            expected = 'workspace-product:' + sha256(json.dumps([path, digest, size], ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
            if ref != expected or not any(p.get('path') == path and p.get('ref') == ref for p in state.get('active_products', [])):
                continue
            products.append({'path': path, 'host_artifact_id': file_artifact_id(path, digest), 'sha256': digest,
                'size_bytes': size, 'presentation_role': 'primary' if path in core else 'support'})
        limitations = state.get('limitations', [])
        if not isinstance(limitations, list) or any(not isinstance(text, str) for text in limitations):
            raise ValueError('delivery presentation limitations are invalid')
        return {'schema': 'capstone-native-delivery-presentation/1', 'thread_id': owner['thread_id'],
            'work_id': owner['work_id'], 'attempt_id': attempt_id, 'task_id': task_id,
            'checkpoint': {'ref': note['note_id'], 'revision': view['research_revision'],
                'sha256': sha256(note['text'].encode()).hexdigest()},
            'delivery_status': 'limited' if state['phase'] == 'limited' else 'completed',
            'delivery_limitations': limitations, 'products': products}
    return None


def graph_delivery_presentation(view, *, task_id, attempt_id, binding):
    """Project explicitly selected graph results; retain exact file identities."""
    from .native_research_bridge import checked_graph_progress
    owner = binding.get('cycle_owner')
    prefix = 'runtime.checkpoint.' + sha256(task_id.encode()).hexdigest()[:20] + '.'
    notes = (view.get('state') or {}).get('notes', [])
    for note in reversed(notes):
        if not isinstance(note, dict) or not note.get('note_id', '').startswith(prefix):
            continue
        saved = json.loads(note['text'])
        if not isinstance(saved, dict):
            raise ValueError('graph delivery checkpoint is invalid')
        revision = saved.get('committed_revision')
        checkpoint = {'ref': note['note_id'], 'revision': revision}
        checked_graph_progress({**saved.get('public_progress', {}), 'checkpoint': checkpoint},
            binding=binding, task_id=task_id, attempt_id=attempt_id, view=view)
        delivery = saved.get('delivery')
        if delivery is None:
            return None
        if (not isinstance(delivery, dict) or set(delivery) != {'outcome', 'delivery_result_refs',
                'delivery_product_refs', 'limitations', 'summary'}
                or delivery['outcome'] not in {'success', 'limited', 'failure'}
                or not isinstance(delivery['summary'], str) or not delivery['summary'].strip()):
            raise ValueError('graph delivery selection is invalid')
        if delivery['outcome'] == 'failure':
            return None
        for key in ('delivery_result_refs', 'delivery_product_refs', 'limitations'):
            values = delivery[key]
            if (not isinstance(values, list) or any(not isinstance(item, str) or not item.strip() for item in values)
                    or len(values) != len(set(values))):
                raise ValueError('graph delivery references or limitations are invalid')
        if delivery['outcome'] == 'limited' and not delivery['limitations']:
            raise ValueError('limited graph delivery requires explicit limitations')
        public_delivery = next((event for event in reversed(saved['public_progress'].get('events', []))
            if isinstance(event, dict) and event.get('kind') == 'graph_delivery_committed'), None)
        if (not isinstance(public_delivery, dict) or set(public_delivery) != {'kind', *delivery}
                or any(public_delivery[key] != delivery[key] for key in (
                    'outcome', 'delivery_result_refs', 'delivery_product_refs'))
                or not isinstance(public_delivery['limitations'], list)
                or len(public_delivery['limitations']) != len(delivery['limitations'])
                or any(not isinstance(text, str) or not text.strip() for text in public_delivery['limitations'])):
            raise ValueError('graph delivery has no committed public closure')
        state, admitted, failed_artifacts, selected_results = saved['snapshot'], set(), set(), []
        for ref in delivery['delivery_result_refs']:
            result = next((item for item in state.get('results', []) if item.get('result_ref') == ref), None)
            producer = result.get('producer') if isinstance(result, dict) else None
            if not isinstance(result, dict) or not isinstance(producer, dict):
                raise ValueError('graph delivery result is not current and accepted')
            node = state.get('node_states', {}).get(producer.get('step_id'))
            if (not isinstance(node, dict) or result.get('owner') != owner
                    or node.get('phase') not in {'success', 'limited', 'failure'}
                    or node.get('applicability') != 'current'
                    or node.get('execution_revision') != producer.get('execution_revision')
                    or producer.get('attempt_id') != attempt_id
                    or not any(item.get('result_ref') == ref for item in node.get('output_bindings', []))):
                raise ValueError('graph delivery result is not current and accepted')
            admitted.update(result.get('artifact_refs', []))
            selected_results.append(result)
            if node['phase'] == 'failure':
                failed_artifacts.update(result.get('artifact_refs', []))
        if delivery['outcome'] == 'success' and any(
                node.get('phase') != 'success' or node.get('applicability') != 'current'
                for node in state.get('node_states', {}).values()):
            raise ValueError('graph delivery has unsettled or stale work')
        products = []
        results_by_ref = {item['result_ref']: item for item in [
            *state.get('external_results', []), *state.get('results', [])]}
        def lineage_grants(result, artifact_ref, available, visited):
            identity = result['result_ref']
            if identity in visited or artifact_ref not in result.get('artifact_refs', []):
                return []
            visited.add(identity)
            direct = [item for item in available if item.get('action_id') == result['producer']['action_id']]
            if direct:
                return direct
            inherited = []
            for consumed in result.get('consumed_results', []):
                if consumed in results_by_ref:
                    inherited.extend(lineage_grants(results_by_ref[consumed], artifact_ref, available, visited))
            return inherited
        for ref in delivery['delivery_product_refs']:
            relevant = [result for result in selected_results if ref in result.get('artifact_refs', [])]
            available = [item for item in saved.get('products', []) if item.get('ref') == ref
                and item.get('owner') == owner and item.get('attempt_id') == attempt_id and item.get('status') == 'ready']
            candidates = []
            for result in relevant:
                selected_grants = lineage_grants(result, ref, available, set())
                if not selected_grants:
                    raise ValueError('graph delivery result has no matching artifact grant')
                candidates.extend(selected_grants)
            if ref not in admitted or not candidates:
                raise ValueError('graph delivery product is not admitted')
            product = candidates[0]
            if any(any(item.get(key) != product.get(key) for key in ('path', 'sha256', 'bytes'))
                   for item in candidates):
                raise ValueError('graph delivery file reference changed identity')
            path, digest, size = product.get('path'), product.get('sha256'), product.get('bytes')
            if (not isinstance(path, str) or not publishable_product_path(path)
                    or '\\' in path or PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts
                    or str(PurePosixPath(path)) != path or not isinstance(digest, str)
                    or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest)
                    or type(size) is not int or size < 1):
                raise ValueError('graph delivery file identity is invalid')
            expected = 'workspace-product:' + sha256(json.dumps(
                [path, digest, size], ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
            if ref != expected:
                raise ValueError('graph delivery file version changed')
            roles = set()
            for candidate in candidates:
                selected_roles = candidate.get('roles', [candidate['role']] if 'role' in candidate else [])
                if (not isinstance(selected_roles, list) or not selected_roles
                        or any(not isinstance(role, str) or role not in ROLES for role in selected_roles)
                        or len(selected_roles) != len(set(selected_roles))):
                    raise ValueError('graph delivery product roles are invalid')
                roles.update(selected_roles)
            role = 'primary' if 'primary' in roles else 'reproduction' if 'reproduction' in roles else 'support'
            if role == 'primary' and ref in failed_artifacts:
                raise ValueError('failed graph result cannot become primary delivery')
            products.append({'path': path, 'host_artifact_id': file_artifact_id(path, digest),
                'sha256': digest, 'size_bytes': size,
                'presentation_role': role})
        if state.get('output_mode') == 'files' and not any(
                product['presentation_role'] == 'primary' for product in products):
            raise ValueError('graph file delivery has no selected saved products')
        return {'schema': 'capstone-native-delivery-presentation/1', 'thread_id': owner['thread_id'],
            'work_id': owner['work_id'], 'attempt_id': attempt_id, 'task_id': task_id,
            'checkpoint': {**checkpoint, 'sha256': sha256(note['text'].encode()).hexdigest()},
            'delivery_status': 'limited' if delivery['outcome'] == 'limited' else 'completed',
            'delivery_limitations': public_delivery['limitations'], 'products': products}
    return None


def presentation_key(thread_id, attempt_id, task_id):
    import re
    if any(not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value)
           for value in (thread_id, attempt_id, task_id)):
        raise ValueError('delivery presentation identity is invalid')
    return 'native-product-presentations/' + thread_id + '/' + attempt_id + '/' + task_id + '.json'


def save_presentation(objects, receipt):
    from .application_capacity import require_capacity
    data = json.dumps(receipt, ensure_ascii=False, allow_nan=False).encode()
    require_capacity('control_document_bytes', len(data), 'native_delivery_presentation')
    objects.put(presentation_key(receipt['thread_id'], receipt['attempt_id'], receipt['task_id']), data, 'application/json')


def presentation_for_artifact(item, objects, cache=None):
    """Enrich immutable old events; never change their identity or bytes."""
    if objects is None or item.get('presentation_role') is not None or item.get('source_status') != 'completed':
        return item
    from .application_capacity import limits, require_capacity
    owner = (item['thread_id'], item['producer_attempt_id'], item['task_id'])
    cache = {} if cache is None else cache
    if owner not in cache:
        try:
            raw = objects.get(presentation_key(*owner), limits.control_document_bytes)
            require_capacity('control_document_bytes', len(raw), 'native_delivery_presentation')
            cache[owner] = json.loads(raw)
        except (KeyError, FileNotFoundError):
            cache[owner] = None
        except Exception as error:
            response = getattr(error, 'response', None)
            if isinstance(response, dict) and response.get('Error', {}).get('Code') in {'NoSuchKey', 'NotFound', '404'}:
                cache[owner] = None
            else:
                raise
    receipt = cache[owner]
    if (not isinstance(receipt, dict) or receipt.get('schema') != 'capstone-native-delivery-presentation/1'
            or (receipt.get('thread_id'), receipt.get('attempt_id'), receipt.get('task_id')) != owner
            or receipt.get('work_id') != item.get('work_id')
            or receipt.get('delivery_status') not in {'limited', 'completed'}):
        return item
    selected = next((product for product in receipt.get('products', [])
        if product.get('host_artifact_id') == item['host_artifact_id'] and product.get('sha256') == item['sha256']
        and product.get('size_bytes') == item['size_bytes']), None)
    if selected is None or selected.get('presentation_role') not in ROLES:
        return item
    limits_text = receipt.get('delivery_limitations')
    if not isinstance(limits_text, list) or any(not isinstance(text, str) for text in limits_text):
        raise ValueError('delivery presentation limitations are invalid')
    return {**item, 'presentation_role': selected['presentation_role'], 'delivery_status': receipt['delivery_status'],
            'delivery_limitations': limits_text}


def export_committed_presentation(root, objects, *, thread_id, work_id, attempt_id, task_id):
    """Operator repair from the existing hash-verified Kernel ledger; no writes to it."""
    from capability_agent.application import ApplicationContextStore
    from capability_agent.application.workspace import ApplicationWorkspace
    from capability_agent._safe_files import read_bound_regular_path
    owner = {'thread_id': thread_id, 'work_id': work_id}
    storage = 'study-' + sha256(json.dumps(owner, sort_keys=True).encode()).hexdigest()[:48]
    workspace = ApplicationWorkspace.open_existing(Path(root), run_id=storage)
    binding = json.loads(read_bound_regular_path(workspace.core_path / 'research-binding.json'))
    turn = json.loads(read_bound_regular_path(workspace.turns_path / (attempt_id + '.json')))
    if (binding.get('owner') != owner or turn.get('thread_id') != thread_id or turn.get('attempt_id') != attempt_id):
        raise ValueError('delivery presentation research owner changed')
    research = ApplicationContextStore.replay(workspace).core.research
    if research is None or research.research_id != binding['research_id']:
        raise ValueError('delivery presentation research identity changed')
    # The retained checkpoint carries the frozen goal revision; verify it against
    # this Attempt's immutable TaskContext rather than the Work's current goal.
    task_context = turn.get('task_context', {})
    expected_owner = {**owner, 'research_id': research.research_id, 'goal_revision': task_context['goal_revision']}
    if task_context.get('binding') != {**owner, 'research_id': research.research_id}:
        raise ValueError('delivery presentation Work binding changed')
    view = {'research_revision': research.revision, 'state': research.model_dump(mode='json')}
    receipt = delivery_presentation(view, task_id=task_id, attempt_id=attempt_id, owner=expected_owner)
    if receipt is None:
        raise ValueError('no committed terminal delivery selection')
    save_presentation(objects, receipt)
    return receipt
