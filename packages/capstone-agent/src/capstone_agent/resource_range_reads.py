"""Application-owned bounded reads with durable, exact retry receipts."""
import base64
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from hashlib import sha256
import json
import re
import secrets
from threading import BoundedSemaphore
import time

from .application_capacity import limits, require_capacity
from .resource_manifest import checked_resource
from .thread_materials import _mutate, _write_event
from .thread_resources import ResourceUploads

# A timeout must not allow an unbounded number of blocked storage operations.
_IO = ThreadPoolExecutor(max_workers=8, thread_name_prefix='resource-range')
_SLOTS = BoundedSemaphore(8)
_EVENT = 'resource_range_read'


class ResourceRangeReads:
    def __init__(self, service, objects):
        self.service, self.objects = service, objects

    def _io(self, fn, deadline, checkpoint):
        checkpoint()
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not _SLOTS.acquire(blocking=False):
            raise ValueError('resource range I/O deadline or capacity exceeded')
        def execute():
            try:
                return fn()
            finally:
                _SLOTS.release()
        try:
            future = _IO.submit(execute)
        except BaseException:
            _SLOTS.release()
            raise
        while True:
            checkpoint()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError('resource range I/O deadline exceeded')
            try:
                result = future.result(timeout=min(remaining, 0.05))
                checkpoint()
                return result
            except TimeoutError:
                continue

    def _records(self, thread, connection=None, *, attempt=None, request_id=None, read_id=None, after=0, limit=1025):
        if hasattr(self.service, '_lock'):
            from itertools import islice
            return [(e.event_seq,e.payload) for e in islice((e for e in self.service._events
                if e.thread_id == thread and e.event_type == _EVENT and e.event_seq > after
                and (attempt is None or e.payload['attempt_id']==attempt)
                and (request_id is None or e.payload['request_id']==request_id)
                and (read_id is None or e.payload['read_id']==read_id)),limit)]
        if connection is None:
            with self.service._connect() as opened:
                return self._records(thread, opened, attempt=attempt, request_id=request_id, read_id=read_id, after=after, limit=limit)
        return [(r['event_seq'],r['payload']) for r in connection.execute(
            "SELECT event_seq,payload FROM capstone_thread_events WHERE thread_id=%s AND event_type=%s AND event_seq>%s "
            "AND (%s::text IS NULL OR payload->>'attempt_id'=%s) "
            "AND (%s::text IS NULL OR payload->>'request_id'=%s) "
            "AND (%s::text IS NULL OR payload->>'read_id'=%s) ORDER BY event_seq LIMIT %s",
            (thread,_EVENT,after,attempt,attempt,request_id,request_id,read_id,read_id,limit)).fetchall()]

    def _usage(self, thread, attempt, connection):
        if connection is not None:
            row=connection.execute("SELECT COALESCE(SUM((payload->>'length')::bigint),0) AS bytes, COUNT(*) AS count "
                "FROM capstone_thread_events WHERE thread_id=%s AND event_type=%s AND payload->>'attempt_id'=%s",
                (thread,_EVENT,attempt)).fetchone()
            return row['bytes'],row['count']
        records=(e.payload for e in self.service._events if e.thread_id==thread and e.event_type==_EVENT and e.payload['attempt_id']==attempt)
        total=count=0
        for record in records:
            total+=record['length']
            count+=1
        return total,count

    def _grant(self, thread, attempt, manifest=None, connection=None):
        if hasattr(self.service, '_lock'):
            self.service._check_thread(thread)
            record = self.service._attempts.get(attempt)
            submission = None if record is None else record.get('submission')
        else:
            if connection is None:
                with self.service._connect() as opened:
                    return self._grant(thread, attempt, manifest, opened)
            record = connection.execute('SELECT submission_snapshot FROM capstone_thread_attempts WHERE thread_id=%s AND attempt_id=%s',
                                        (thread, attempt)).fetchone()
            submission = None if record is None else record['submission_snapshot']
        if record is None:
            raise ValueError('attempt not found in this Thread')
        if manifest is not None and manifest not in [checked_resource(r) for r in (submission or {}).get('_resource_manifests', [])]:
            raise ValueError('resource not admitted for this attempt')

    @staticmethod
    def _key(receipt):
        return 'resource-range-reads/' + sha256(receipt['thread_id'].encode()).hexdigest() + '/' + receipt['read_id']

    def read(self, thread_id, attempt_id, task_id, manifest, request, *, checkpoint=lambda: None):
        canonical = checked_resource(dict(manifest))
        if (not isinstance(request, dict) or set(request) != {'schema','request_id','resource_id','offset','length'}
                or request['schema'] != 'capstone-resource-range-request/1'
                or not isinstance(request['request_id'], str) or not re.fullmatch('[a-f0-9]{64}', request['request_id'])
                or request['resource_id'] != canonical['resource_id'] or canonical['thread_id'] != thread_id
                or type(request['offset']) is not int or type(request['length']) is not int
                or request['offset'] < 0 or request['length'] <= 0
                or request['offset'] + request['length'] > min(canonical['size_bytes'], 9007199254740991)
                or not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', task_id)):
            raise ValueError('invalid resource range request')
        require_capacity('resource_read_bytes', request['length'], phase='resource.read')
        deadline = time.monotonic() + limits.resource_read_io_seconds
        checkpoint()
        expected = dict(thread_id=thread_id, attempt_id=attempt_id, task_id=task_id,
                        request_id=request['request_id'], resource=canonical,
                        offset=request['offset'], length=request['length'])
        def find(snapshot, connection):
            self._grant(thread_id, attempt_id, canonical, connection)
            records = self._records(thread_id, connection, attempt=attempt_id, request_id=request['request_id'], limit=1)
            for _, receipt in records:
                if receipt['attempt_id'] == attempt_id:
                    if any(receipt[k] != v for k, v in expected.items()):
                        raise ValueError('resource range request conflict')
                    return receipt
            used,count = self._usage(thread_id,attempt_id,connection)
            require_capacity('resource_read_attempt_bytes', used + request['length'], phase='resource.read')
            require_capacity('resource_read_attempt_count', 1 + count, phase='resource.read')
            return None
        previous = _mutate(self.service, thread_id, find)
        def recover(receipt):
            data = self._io(lambda: self.objects.get(self._key(receipt), receipt['length']), deadline, checkpoint)
            if len(data) != receipt['length'] or sha256(data).hexdigest() != receipt['sha256']:
                raise ValueError('retained resource range integrity failed')
            return {'receipt': receipt, 'content': data}
        if previous:
            return recover(previous)
        uploads = ResourceUploads(self.service, self.objects)
        uid = 'upload_' + canonical['resource_id'].removeprefix('resource_')
        state = uploads._state(thread_id, uid, include_parts=False)
        if state['state'] != 'complete' or checked_resource(state.get('resource')) != canonical:
            raise ValueError('published resource identity changed')
        end = request['offset'] + request['length']
        fragments = []
        for index in range(request['offset'] // state['chunk_bytes'], (end + state['chunk_bytes']-1)//state['chunk_bytes']):
            part_state = uploads._state(thread_id, uid, part_index=index)
            part = part_state['parts'][index]
            data = self._io(lambda p=part: uploads._bytes(thread_id, uid, p), deadline, checkpoint)
            start = index * state['chunk_bytes']
            fragments.append(data[max(0,request['offset']-start):min(len(data),end-start)])
        content = b''.join(fragments)
        if len(content) != request['length']:
            raise ValueError('resource range length changed')
        sample = content[:limits.resource_read_preview_bytes]
        status, text = 'text', None
        try:
            text = sample.decode('utf-8')
            if '\x00' in text:
                status, text = 'binary', None
        except UnicodeDecodeError:
            status = 'invalid-UTF8'
        receipt = dict(schema='capstone-resource-read/1', read_id='read_' + secrets.token_hex(16), **expected,
                       sha256=sha256(content).hexdigest(), preview=dict(bytes_read=len(sample),
                       truncated=len(sample)<len(content), status=status, text=text))
        self._io(lambda: self.objects.put(self._key(receipt), content, 'application/octet-stream'), deadline, checkpoint)
        # Read back before acceptance. Storage corruption cannot create an accepted receipt.
        recover(receipt)
        def accept(snapshot, connection):
            checkpoint()
            previous = find(snapshot, connection)
            if previous:
                return previous
            _write_event(self.service, snapshot, _EVENT, receipt, connection)
            return receipt
        accepted = _mutate(self.service, thread_id, accept)
        return {'receipt': accepted, 'content': content} if accepted == receipt else recover(accepted)

    def detail(self, thread_id, read_id):
        self.service.snapshot(thread_id)
        for _,receipt in self._records(thread_id,read_id=read_id,limit=1):
            if receipt['read_id'] == read_id:
                self._grant(thread_id, receipt['attempt_id'], receipt['resource'])
                return receipt
        raise ValueError('resource read not found in this Thread')

    def page(self, thread_id, attempt_id, limit=100, cursor=None):
        self.service.snapshot(thread_id)
        self._grant(thread_id, attempt_id)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('invalid resource read page limit')
        after = 0
        if cursor is not None:
            try:
                if not isinstance(cursor,str) or len(cursor)>1024:
                    raise ValueError()
                value = json.loads(base64.b64decode(cursor, altchars=b'-_', validate=True))
                if len(cursor)>1024 or set(value) != {'thread','attempt','after'} or value['thread'] != thread_id or value['attempt'] != attempt_id or type(value['after']) is not int or value['after'] < 0:
                    raise ValueError()
                after = value['after']
            except (ValueError, TypeError, KeyError):
                raise ValueError('invalid resource read cursor') from None
        records = self._records(thread_id,attempt=attempt_id,after=after,limit=limit+1)
        items = [r for _,r in records[:limit]]
        next_cursor = None
        if len(records)>limit:
            next_cursor = base64.urlsafe_b64encode(json.dumps(dict(thread=thread_id, attempt=attempt_id, after=records[limit-1][0])).encode()).decode()
        return dict(schema='capstone-resource-read-page/1', items=items, next_cursor=next_cursor)
