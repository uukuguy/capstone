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
from .resource_range_contract import ResourceRangeRejected, ResourceRangePersistenceError, preview_for

# A timeout must not allow an unbounded number of blocked storage operations.
_IO = ThreadPoolExecutor(max_workers=8, thread_name_prefix='resource-range')
_SLOTS = BoundedSemaphore(8)
_EVENT = 'resource_range_read'


class ResourceRangeReads:
    def __init__(self, service, objects):
        self.service, self.objects = service, objects

    def _io(self, fn, deadline, checkpoint, *, on_abandon=None):
        checkpoint()
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not _SLOTS.acquire(blocking=False):
            raise ResourceRangeRejected('resource range I/O deadline or capacity exceeded','resource_range_unavailable')
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
        try:
            while True:
                checkpoint()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ResourceRangeRejected('resource range I/O deadline exceeded','resource_range_unavailable')
                try:
                    result = future.result(timeout=min(remaining, 0.05))
                    checkpoint()
                    return result
                except TimeoutError:
                    continue
        except BaseException:
            if on_abandon is not None:
                future.add_done_callback(lambda _: on_abandon())
            raise

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

    def _abandoned(self,thread,read_id,connection):
        if connection is None:
            return any(e.thread_id==thread and e.event_type=='resource_range_abandoned'
                       and e.payload['read_id']==read_id for e in self.service._events)
        return connection.execute("SELECT 1 FROM capstone_thread_events WHERE thread_id=%s "
            "AND event_type='resource_range_abandoned' AND payload->>'read_id'=%s LIMIT 1",
            (thread,read_id)).fetchone() is not None

    def _abandon_candidate(self,thread,candidate):
        def abandon(snapshot,connection):
            if self._records(thread,connection,read_id=candidate['read_id'],limit=1):
                return False
            if not self._abandoned(thread,candidate['read_id'],connection):
                _write_event(self.service,snapshot,'resource_range_abandoned',
                             dict(read_id=candidate['read_id']),connection)
            return True
        return _mutate(self.service,thread,abandon)

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
            raise ResourceRangeRejected('attempt not found in this Thread')
        if manifest is not None and manifest not in [checked_resource(r) for r in (submission or {}).get('_resource_manifests', [])]:
            raise ResourceRangeRejected('resource not admitted for this attempt')

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
            raise ResourceRangeRejected('invalid resource range request')
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
                        raise ResourceRangeRejected('resource range request conflict')
                    return receipt
            used,count = self._usage(thread_id,attempt_id,connection)
            require_capacity('resource_read_attempt_bytes', used + request['length'], phase='resource.read')
            require_capacity('resource_read_attempt_count', 1 + count, phase='resource.read')
            return None
        previous = _mutate(self.service, thread_id, find)
        def recover(receipt):
            try:
                data = self._io(lambda: self.objects.get(self._key(receipt), receipt['length']), deadline, checkpoint)
            except (OSError,KeyError,ValueError) as error:
                raise ResourceRangePersistenceError('retained resource range is unavailable') from error
            if len(data) != receipt['length'] or sha256(data).hexdigest() != receipt['sha256']:
                raise ResourceRangePersistenceError('retained resource range integrity failed')
            return {'receipt': receipt, 'content': data}
        if previous:
            return recover(previous)
        uploads = ResourceUploads(self.service, self.objects)
        try:
            state = uploads._published_state(
                thread_id, canonical['resource_id'], canonical['version'], include_parts=False)
        except ValueError as error:
            raise ResourceRangeRejected('resource range source is unavailable','resource_range_unavailable') from error
        if state['state'] != 'complete' or checked_resource(state.get('resource')) != canonical:
            raise ResourceRangeRejected('published resource identity changed','resource_range_unavailable')
        uid = state['upload_id']
        end = request['offset'] + request['length']
        fragments = []
        for index in range(request['offset'] // state['chunk_bytes'], (end + state['chunk_bytes']-1)//state['chunk_bytes']):
            part_state = uploads._state(thread_id, uid, part_index=index)
            part = part_state['parts'][index]
            try:
                data = self._io(lambda p=part: uploads._bytes(thread_id, uid, p), deadline, checkpoint)
            except ResourceRangeRejected:
                raise
            except (OSError,KeyError,ValueError) as error:
                raise ResourceRangeRejected('resource range source integrity or availability failed','resource_range_unavailable') from error
            start = index * state['chunk_bytes']
            fragments.append(data[max(0,request['offset']-start):min(len(data),end-start)])
        content = b''.join(fragments)
        if len(content) != request['length']:
            raise ValueError('resource range length changed')
        receipt = dict(schema='capstone-resource-read/1', read_id='read_' + secrets.token_hex(16), **expected,
                       sha256=sha256(content).hexdigest(), preview=preview_for(content,limits.resource_read_preview_bytes))
        # A crash before acceptance must leave a durable owned cleanup source.
        _mutate(self.service,thread_id,lambda snapshot,connection: _write_event(self.service,snapshot,
            'resource_range_candidate',dict(thread_id=thread_id,read_id=receipt['read_id'],created_at=time.time()),connection))
        def discard():
            self.objects.delete(self._key(receipt))
        try:
            self._io(lambda: self.objects.put(self._key(receipt), content, 'application/octet-stream'), deadline, checkpoint,
                     on_abandon=discard)
            # Read back before acceptance. Storage corruption cannot create an accepted receipt.
            recover(receipt)
        except BaseException as error:
            # Unique candidate keys cannot identify another request's winner.
            self._io(discard,time.monotonic()+limits.resource_read_io_seconds,lambda: None)
            if isinstance(error,(OSError,KeyError,ResourceRangeRejected)):
                raise ResourceRangePersistenceError('resource range retention failed') from error
            raise
        def accept(snapshot, connection):
            checkpoint()
            previous = find(snapshot, connection)
            if previous:
                return previous
            if self._abandoned(thread_id,receipt['read_id'],connection):
                raise ResourceRangePersistenceError('resource range candidate was abandoned')
            checkpoint()
            if time.monotonic()>=deadline:
                raise ResourceRangeRejected('resource range acceptance deadline exceeded','resource_range_unavailable')
            _write_event(self.service, snapshot, _EVENT, receipt, connection)
            return receipt
        try:
            accepted = _mutate(self.service, thread_id, accept)
        except BaseException:
            # A failed acknowledgement may follow a committed acceptance. Check
            # the durable identity before removing any candidate object.
            if self._abandon_candidate(thread_id,receipt):
                self._io(discard,time.monotonic()+limits.resource_read_io_seconds,lambda: None)
            raise
        if accepted!=receipt:
            self._io(discard,time.monotonic()+limits.resource_read_io_seconds,lambda: None)
        return {'receipt': accepted, 'content': content} if accepted == receipt else recover(accepted)

    def reconcile(self,thread_id,*,after=0,limit=100):
        """Remove expired unaccepted candidates; return a bounded maintenance cursor.

        The grace period exceeds the maximum active storage deadline. A late
        write in this process also has its own completion cleanup callback.
        """
        self.service.snapshot(thread_id)
        if type(after) is not int or after<0 or type(limit) is not int or not 1<=limit<=100:
            raise ValueError('invalid range reconciliation cursor')
        cutoff=time.time()-2*limits.resource_read_io_seconds
        if hasattr(self.service,'_lock'):
            from itertools import islice
            rows=[(e.event_seq,e.payload) for e in islice((e for e in self.service._events
                if e.thread_id==thread_id and e.event_type=='resource_range_candidate' and e.event_seq>after
                and e.payload['created_at']<cutoff),limit)]
        else:
            with self.service._connect() as connection:
                rows=[(r['event_seq'],r['payload']) for r in connection.execute(
                    "SELECT event_seq,payload FROM capstone_thread_events WHERE thread_id=%s AND event_type='resource_range_candidate' "
                    "AND event_seq>%s AND (payload->>'created_at')::double precision<%s ORDER BY event_seq LIMIT %s",
                    (thread_id,after,cutoff,limit)).fetchall()]
        for _,candidate in rows:
            # Fence under the same Thread lock as acceptance, then perform
            # storage deletion after the transaction has ended. A candidate
            # can never be accepted after this durable tombstone commits.
            if self._abandon_candidate(thread_id,candidate):
                self._io(lambda c=candidate:self.objects.delete(self._key(c)),
                         time.monotonic()+limits.resource_read_io_seconds,lambda:None)
        return rows[-1][0] if rows else after

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
