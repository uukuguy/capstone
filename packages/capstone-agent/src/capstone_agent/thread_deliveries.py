"""Explicit requested reports over the existing Thread command/event ledger.

This application adapter publishes documents, not another execution runtime.
Process records remain instruction-scoped; only an explicit delivery request
creates a task-scoped artifact. Content uses the existing private ObjectStore.
"""
from dataclasses import replace
from collections.abc import Mapping
from hashlib import sha256
import json
import re
import secrets

from psycopg.types.json import Jsonb

from .thread_protocol import CommandReceipt, EventEnvelope
from .result_projection import ResultProjection
from .session_title import SessionTitle
from .thread_service import ThreadNotFound, _StoredCommand, _now


TERMINALS = {'attempt_completed', 'attempt_failed', 'attempt_cancelled', 'attempt_interrupted'}
EVENT_TYPES = TERMINALS | {'delivery_published', 'command_accepted', 'result_projection_part'}
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}')
MAX_DELIVERY_FILE_BYTES = 4 * 1024 * 1024

from .application_capacity import limits, require_capacity


def _request(value):
    fields = {'schema', 'command_id', 'idempotency_key', 'request_id', 'expected_revision',
              'work_id', 'trigger_attempt_id', 'title', 'scope', 'format', 'supporting_process_ids'}
    if isinstance(value, dict) and value.get('format') == 'native-file':
        fields.add('source_artifact')
    if not isinstance(value, dict) or set(value) != fields or value['schema'] != 'capstone-delivery-request/1':
        raise ValueError('invalid delivery request')
    for key in ('command_id', 'idempotency_key', 'request_id', 'trigger_attempt_id'):
        if not isinstance(value[key], str) or not ID.fullmatch(value[key]):
            raise ValueError('invalid delivery identity')
    if value['work_id'] is not None and (not isinstance(value['work_id'], str) or not ID.fullmatch(value['work_id'])):
        raise ValueError('invalid delivery Work')
    if (type(value['expected_revision']) is not int or value['expected_revision'] < 0
            or value['format'] not in ('markdown', 'native-file')):
        raise ValueError('unsupported delivery format or invalid revision')
    if value['format'] == 'native-file':
        source = value['source_artifact']
        if (not isinstance(source, dict) or set(source) != {'attempt_id', 'artifact_id'}
                or any(not isinstance(item, str) or not ID.fullmatch(item) for item in source.values())):
            raise ValueError('invalid native artifact reference')
    for key, maximum in (('title', limits.ui_delivery_title_chars), ('scope', limits.ui_delivery_scope_chars)):
        text = value[key]
        if isinstance(text, str):
            require_capacity('ui_delivery_title_chars' if key == 'title' else 'ui_delivery_scope_chars', len(text), phase='delivery.request')
        if not isinstance(text, str) or not text.strip() or len(text) > maximum or any(ord(c) < 32 and c not in '\n\t' for c in text):
            raise ValueError('invalid delivery text')
    if '\n' in value['title'] or '\t' in value['title']:
        raise ValueError('invalid delivery title')
    refs = value['supporting_process_ids']
    if isinstance(refs, list):
        require_capacity('ui_delivery_support_count', len(refs), phase='delivery.request')
    if (not isinstance(refs, list) or not 1 <= len(refs) <= limits.ui_delivery_support_count
            or any(not isinstance(ref, str) or not ref.startswith('process_') or not ID.fullmatch(ref) for ref in refs)
            or len(set(refs)) != len(refs)):
        raise ValueError('invalid supporting process references')
    return json.loads(json.dumps(value, ensure_ascii=False))


def _events(service, thread_id, connection=None, *, source_attempt_ids=None):
    if connection is None:
        service._check_thread(thread_id)
        return [event for event in service._events if event.event_type in EVENT_TYPES and event.visibility == 'public'
                and (source_attempt_ids is None or event.event_type == 'delivery_published' or event.attempt_id in source_attempt_ids)]
    rows = connection.execute('''SELECT * FROM capstone_thread_events
        WHERE thread_id=%s AND event_type=ANY(%s) AND visibility='public'
        AND (%s::text[] IS NULL OR event_type='delivery_published' OR attempt_id=ANY(%s)) ORDER BY event_seq''',
        (thread_id, sorted(EVENT_TYPES), source_attempt_ids, source_attempt_ids)).fetchall()
    return [service._event_from_row(row) for row in rows]


def _key(thread_id, delivery):
    suffix = '.file' if delivery['format'] == 'native-file' else '.md'
    return 'thread-deliveries/' + sha256(thread_id.encode()).hexdigest() + '/' + delivery['artifact_id'] + '/' + str(delivery['revision']) + '/' + delivery['content_digest'] + suffix


def _prepare(objects, snapshot, events, request, native_reader=None):
    previous = [event.payload['delivery'] for event in events if event.event_type == 'delivery_published'
                and event.payload['delivery']['request']['request_id'] == request['request_id']]
    revision = max((item['revision'] for item in previous), default=0)
    if request['expected_revision'] != revision:
        return None, 'revision_conflict'
    if previous and previous[-1]['work_id'] != request['work_id']:
        raise ValueError('delivery request cannot move between Works')
    terminals = {event.attempt_id: event for event in events if event.event_type in TERMINALS}
    trigger = terminals.get(request['trigger_attempt_id'])
    if trigger is None:
        raise ValueError('trigger Attempt is not a saved terminal process in this Thread')
    work_id = request['work_id']
    if work_id is not None and not any(item['work_id'] == work_id for item in snapshot.works):
        raise ValueError('delivery Work is not in this Thread')
    if trigger.payload.get('work_id') != work_id:
        raise ValueError('delivery trigger belongs to another Work')
    sources = []
    for ref in request['supporting_process_ids']:
        event = terminals.get(ref.removeprefix('process_'))
        if event is None:
            raise ValueError('supporting process is not in this Thread')
        sources.append(event)
    # Cross-Work support is explicit in this request, never an evidence grant.
    artifact_id = 'delivery_' + sha256((snapshot.thread_id + '\0' + request['request_id']).encode()).hexdigest()[:32]
    document = {
        'schema': 'capstone-delivery/1', 'scope': 'task', 'thread_id': snapshot.thread_id,
        'run_id': snapshot.run.run_id, 'work_id': work_id, 'artifact_id': artifact_id,
        'revision': revision + 1, 'title': request['title'], 'request': {key: value for key, value in request.items()
            if key not in {'schema', 'command_id', 'idempotency_key', 'expected_revision'}},
        'request_revision': revision + 1, 'trigger_attempt_id': trigger.attempt_id,
        'producer_attempt_id': None, 'producer_command_id': request['command_id'],
        'supporting_process_ids': list(request['supporting_process_ids']),
        'supporting_process_refs': [{'process_id': 'process_' + event.attempt_id,
            'attempt_id': event.attempt_id, 'turn_id': event.turn_id, 'work_id': event.payload.get('work_id'),
            'run_id': event.run_id, 'event_id': event.event_id, 'event_seq': event.event_seq,
            'model_context_id': event.model_context_id, 'selection_revision': event.selection_revision}
            for event in sources],
        'supporting_statuses': [{'process_id': 'process_' + event.attempt_id,
                                'status': event.event_type.removeprefix('attempt_')} for event in sources],
        'replaces_revision': revision or None, 'generation_status': 'completed',
        'check_status': 'content_integrity_checked', 'requirements_status': 'not_independently_checked',
        'media_type': 'text/markdown; charset=utf-8', 'format': 'markdown',
        'generator': 'saved-process-report/1', 'created_at': _now(),
    }
    maximum = limits.delivery_file_bytes
    if request['format'] == 'native-file':
        source = request['source_artifact']
        owner = terminals.get(source['attempt_id'])
        if (owner is None or 'process_' + source['attempt_id'] not in request['supporting_process_ids']
                or owner.payload.get('work_id') != work_id):
            raise ValueError('selected file must belong to a supporting process in the requested Work')
        if native_reader is None:
            raise OSError('native artifact reader unavailable')
        descriptor, content = native_reader(source['attempt_id'], source['artifact_id'])
        if (descriptor['thread_id'] != snapshot.thread_id or descriptor['attempt_id'] != source['attempt_id']
                or descriptor['artifact_id'] != source['artifact_id'] or descriptor['work_id'] != work_id):
            raise ValueError('native artifact ownership mismatch')
        maximum = limits.delivery_file_bytes
        if (not isinstance(content, bytes) or len(content) != descriptor['size_bytes']
                or sha256(content).hexdigest() != descriptor['sha256']):
            raise OSError('native artifact integrity mismatch')
        status = descriptor['source_status']
        generation = status if status != 'completed' else owner.event_type.removeprefix('attempt_')
        document.update(format='native-file', file_name=descriptor['file_name'], media_type=descriptor['media_type'],
            source_status=status, generation_status=generation, source_artifact=dict(descriptor),
            producer_attempt_id=descriptor['producer_attempt_id'], generator='explicit-native-file-adoption/1')
    else:
        content = _render(snapshot, events, sources, document).encode('utf-8')
        document['file_name'] = artifact_id + '.md'
    if len(content) > maximum:
        raise ValueError('requested report exceeds artifact capacity')
    document.update(byte_size=len(content), content_digest=sha256(content).hexdigest())
    if len(json.dumps({'delivery': document}, ensure_ascii=False).encode()) > limits.control_document_bytes:
        raise ValueError('delivery relationships exceed event capacity')
    # Store first. A failed ledger transaction leaves only an unreachable object.
    try:
        key = _key(snapshot.thread_id, document)
        objects.put(key, content, document['media_type'])
        saved = objects.get(key, maximum)
        if len(saved) != len(content) or sha256(saved).hexdigest() != document['content_digest']:
            raise ValueError('delivery storage verification failed')
    except Exception:
        raise OSError('delivery object storage failed') from None
    return document, None


def _render(snapshot, events, sources, delivery):
    requested = delivery['request']
    lines = ['# ' + requested['title'], '', '## 交付要求', '', requested['scope'], '',
             '## 来源与检查范围', '',
             '本文件是用户明确请求的过程资料汇编，只整理已保存的执行过程与计算结果。它不执行新的业务分析，也不声明满足任意报告要求。历史结果不因此取得当前运行证据资格。',
             '文件完整性已核对；交付要求的业务满足情况尚未独立核验。失败和缺口保留如下。', '']
    accepted = {event.attempt_id: event for event in events if event.event_type == 'command_accepted'
                and event.payload.get('kind') in {'send_auto', 'send_professional', 'send_ordinary', 'send_message'}}
    for event in sources:
        lines.extend(['## 执行过程 ' + event.attempt_id, '',
                      '- 状态：' + event.event_type.removeprefix('attempt_'),
                      '- 过程引用：process_' + event.attempt_id,
                      '- 原始事件游标：' + str(event.event_seq), ''])
        source = accepted.get(event.attempt_id)
        if source is not None:
            payload = source.payload.get('payload', source.payload)
            text = payload.get('text') if isinstance(payload, dict) else None
            if isinstance(text, str):
                lines.extend(['### 原指令', '', text, ''])
        projections = _source_projections(snapshot, events, event)
        if not projections:
            lines.extend(['当前结果目录无可嵌入的结构化计算投影；请沿过程引用查看原始记录。未补造计算数值。', ''])
        for projection in projections:
            # Only admitted public projections, never diagnostic/tool raw objects.
            lines.extend(['### 已保存计算结果', '', '- 结果引用：' + str(projection.result_ref),
                          '- 模型：' + projection.model_id + '；修订：' + projection.model_revision,
                          '- 状态：' + projection.status, ''])
            for metric in projection.summary:
                lines.append('- ' + metric.label + '：' + str(metric.value) + ((' ' + metric.unit) if metric.unit else ''))
            for table in projection.tables:
                lines.extend(['', '#### ' + table.title, '',
                              '| ' + ' | '.join(_cell(column.label + ((' (' + column.unit + ')') if column.unit else '')) for column in table.columns) + ' |',
                              '| ' + ' | '.join('---' for _ in table.columns) + ' |'])
                for row in table.rows:
                    lines.append('| ' + ' | '.join(_cell(row.cells.get(column.column_id)) for column in table.columns) + ' |')
                if table.pagination is not None:
                    lines.extend(['', f'表格预览 {len(table.rows)} / {table.pagination.total_rows} 行；完整表引用：{table.pagination.manifest_ref}', ''])
            if projection.evidence_refs:
                lines.extend(['', '历史依据引用：' + ', '.join(projection.evidence_refs), ''])
        if event.event_type != 'attempt_completed':
            lines.extend(['### 未完成事项', '', '该执行没有完成，不能将其状态解释为已验证成功；已有其他结果仍保持各自状态。', ''])
    return '\n'.join(lines) + '\n'


def _source_projections(snapshot, events, terminal):
    """Use immutable admitted ledger data even after the snapshot window moves."""
    documents = list(terminal.payload.get('result_projections', ()))
    for manifest in terminal.payload.get('result_projection_manifest', ()):
        parts = [event.payload for event in events if event.event_type == 'result_projection_part'
                 and event.attempt_id == terminal.attempt_id and event.payload.get('result_id') == manifest['result_id']]
        parts.sort(key=lambda part: part['part_index'])
        if [part['part_index'] for part in parts] != list(range(manifest['parts'])):
            raise ValueError('historical result projection parts unavailable')
        documents.append(json.loads(''.join(part['data'] for part in parts)))
    selected = {item.result_id: item for item in snapshot.result_projections if item.attempt_id == terminal.attempt_id}
    for document in documents:
        item = ResultProjection.from_document(document)
        selected[item.result_id] = item
    if selected:
        admission = terminal.payload.get('admission')
        if (not isinstance(admission, Mapping) or admission.get('mode') != 'authority_backed'
                or admission.get('assurance') != 'lineage_verified'):
            raise ValueError('historical projections lack verified terminal admission')
        results = terminal.payload.get('result_refs', ())
        evidence = terminal.payload.get('evidence_refs', ())
        for item in selected.values():
            if (item.thread_id != snapshot.thread_id or item.run_id != terminal.run_id
                    or item.attempt_id != terminal.attempt_id or item.turn_id != terminal.turn_id
                    or item.model_context_id != terminal.model_context_id):
                raise ValueError('historical result projection identity mismatch')
            if item.result_ref not in results or not set(item.evidence_refs) <= set(evidence):
                raise ValueError('historical result projection references are not admitted')
    return list(selected.values())


def _cell(value):
    return ('' if value is None else str(value)).replace('|', '\\|').replace('\n', '<br>')


def _receipt(snapshot, request, *, delivery=None, rejection=None, event_seq=None):
    return CommandReceipt(request['command_id'], request['idempotency_key'], snapshot.thread_id,
        snapshot.run.run_id, 'rejected' if rejection else 'accepted', event_seq, rejection,
        None if delivery is None else {'delivery': delivery})


def _admission_rejection(snapshot, archived):
    if archived:
        return 'thread_archived'
    if snapshot.run.state != 'open':
        return 'run_not_open'
    return None


def _suggest_title(snapshot, delivery):
    """A saved requested delivery can name a session, never replace a user title."""
    current = snapshot.session_title or SessionTitle('工作会话')
    if current.source == 'user' or delivery['generation_status'] != 'completed':
        return snapshot.session_title
    try:
        return current.suggest(delivery['title'][:160].strip(), expected_revision=current.revision,
                               source_ref=delivery['artifact_id'] + ':' + str(delivery['revision']))
    except ValueError:
        # Auxiliary naming must not break artifact persistence.
        return snapshot.session_title


def publish_delivery(service, objects, thread_id, value, *, native_artifact_executor=None):
    """Commit an explicit user request using the existing command/event transaction."""
    request = _request(value)
    source_attempt_ids = sorted({request['trigger_attempt_id'],
        *(ref.removeprefix('process_') for ref in request['supporting_process_ids'])})
    def native_reader(attempt_id, artifact_id):
        from .native_artifact_projection import read_native_artifact
        return read_native_artifact(service, native_artifact_executor, thread_id, attempt_id, artifact_id)
    digest = sha256(json.dumps({'thread_id': thread_id, 'delivery_request': request},
                              sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if hasattr(service, '_lock'):
        with service._lock:
            service._check_thread(thread_id)
            snapshot = service._snapshot
            old = service._commands.get(request['idempotency_key'])
            if old is not None:
                return old.receipt if old.request_hash == digest else _receipt(snapshot, request, rejection='idempotency_conflict')
            if request['command_id'] in service._command_ids:
                return _receipt(snapshot, request, rejection='command_id_conflict')
            delivery, rejection = None, _admission_rejection(snapshot, service._archived)
            if rejection is None:
                delivery, rejection = _prepare(objects, snapshot, _events(service, thread_id, source_attempt_ids=source_attempt_ids), request, native_reader)
            seq = None
            if delivery is not None:
                event = service._append_control_event(event_type='delivery_published', payload={'delivery': delivery})
                seq = event.event_seq
                service._snapshot = replace(snapshot, last_event_seq=seq)
                title = _suggest_title(snapshot, delivery)
                if title is not None and title != snapshot.session_title:
                    named = service._append_control_event(event_type='session_title_changed', payload={
                        'session_title': title.to_document(), 'source_delivery': delivery['artifact_id']})
                    service._snapshot = replace(service._snapshot, last_event_seq=named.event_seq, session_title=title)
            receipt = _receipt(snapshot, request, delivery=delivery, rejection=rejection, event_seq=seq)
            service._commands[request['idempotency_key']] = _StoredCommand(digest, receipt)
            service._command_ids.add(request['command_id'])
            return receipt
    with service._connect() as connection:
        thread = connection.execute('SELECT * FROM capstone_threads WHERE thread_id=%s FOR UPDATE', (thread_id,)).fetchone()
        if thread is None:
            raise ThreadNotFound(thread_id)
        snapshot = service._snapshot_from_row(thread)
        old = connection.execute('SELECT request_hash,receipt FROM capstone_thread_commands WHERE thread_id=%s AND idempotency_key=%s',
                                 (thread_id, request['idempotency_key'])).fetchone()
        if old is not None:
            return CommandReceipt.from_document(old['receipt']) if old['request_hash'] == digest else _receipt(snapshot, request, rejection='idempotency_conflict')
        duplicate = connection.execute('SELECT 1 FROM capstone_thread_commands WHERE thread_id=%s AND command_id=%s', (thread_id, request['command_id'])).fetchone()
        if duplicate:
            return _receipt(snapshot, request, rejection='command_id_conflict')
        delivery, rejection = None, _admission_rejection(snapshot, thread['archived'])
        if rejection is None:
            delivery, rejection = _prepare(objects, snapshot, _events(service, thread_id, connection, source_attempt_ids=source_attempt_ids), request, native_reader)
        seq = None
        if delivery is not None:
            seq = snapshot.last_event_seq + 1
            context = snapshot.active_model_context
            event = EventEnvelope('evt_' + secrets.token_hex(8), seq, 'delivery_published', 1,
                thread_id, snapshot.run.run_id, None, None, None if context is None else context.id,
                None if context is None else context.selection_revision, _now(), 'public', {'delivery': delivery})
            service._insert_event(connection, event)
            title = _suggest_title(snapshot, delivery)
            last_seq = seq
            if title is not None and title != snapshot.session_title:
                last_seq += 1
                named = EventEnvelope('evt_' + secrets.token_hex(8), last_seq, 'session_title_changed', 1,
                    thread_id, snapshot.run.run_id, None, None, None, None, _now(), 'public',
                    {'session_title': title.to_document(), 'source_delivery': delivery['artifact_id']})
                service._insert_event(connection, named)
            connection.execute('UPDATE capstone_threads SET last_event_seq=%s,session_title=%s WHERE thread_id=%s',
                (last_seq, None if title is None else Jsonb(title.to_document()), thread_id))
        receipt = _receipt(snapshot, request, delivery=delivery, rejection=rejection, event_seq=seq)
        connection.execute('INSERT INTO capstone_thread_commands (thread_id,idempotency_key,request_hash,command_id,receipt) VALUES (%s,%s,%s,%s,%s)',
            (thread_id, request['idempotency_key'], digest, request['command_id'], Jsonb(receipt.to_document())))
        return receipt


def delivery_page(service, thread_id, *, before=None, limit=32):
    if type(limit) is int:
        require_capacity('product_page_items', limit, phase='delivery_page')
    if type(limit) is not int or limit < 1 or (before is not None and (type(before) is not int or before < 1)):
        raise ValueError('invalid delivery cursor')
    if hasattr(service, '_lock'):
        with service._lock:
            service._check_thread(thread_id)
            selected = [event for event in reversed(service._events) if event.event_type == 'delivery_published'
                        and (before is None or event.event_seq < before)][:limit + 1]
    else:
        service.snapshot(thread_id)
        with service._connect() as connection:
            rows = connection.execute('''SELECT * FROM capstone_thread_events WHERE thread_id=%s
                AND event_type='delivery_published' AND (%s::bigint IS NULL OR event_seq<%s)
                ORDER BY event_seq DESC LIMIT %s''', (thread_id, before, before, limit + 1)).fetchall()
            selected = [service._event_from_row(row) for row in rows]
    page = selected[:limit]
    return {'schema': 'capstone-deliveries/1', 'thread_id': thread_id,
            'deliveries': [json.loads(json.dumps(event.payload['delivery'])) for event in page],
            'has_more': len(selected) > limit, 'next_before_event_seq': page[-1].event_seq if page else before}


def delivery_metadata(service, thread_id, artifact_id, revision):
    if not isinstance(artifact_id, str) or not ID.fullmatch(artifact_id) or type(revision) is not int or revision < 1:
        raise ValueError('invalid delivery identity')
    before = None
    while True:
        page = delivery_page(service, thread_id, before=before, limit=50)
        delivery = next((item for item in page['deliveries'] if item['artifact_id'] == artifact_id and item['revision'] == revision), None)
        if delivery is not None:
            return delivery
        if not page['has_more']:
            raise KeyError('delivery revision not found')
        before = page['next_before_event_seq']


def read_delivery_content(service, objects, thread_id, artifact_id, revision):
    delivery = delivery_metadata(service, thread_id, artifact_id, revision)
    maximum = limits.delivery_file_bytes if delivery['format'] == 'native-file' else limits.delivery_file_bytes
    try:
        content = objects.get(_key(thread_id, delivery), maximum)
    except Exception:
        raise OSError('delivery object storage unavailable') from None
    if (len(content) > maximum or len(content) != delivery['byte_size']
            or sha256(content).hexdigest() != delivery['content_digest']):
        raise ValueError('delivery content integrity check failed')
    return content
