"""Application composition for verified product membership and adoption."""
from copy import deepcopy
from contextlib import nullcontext
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from types import SimpleNamespace

from .product_series import transition
from .product_series_store import ProductSeriesStore
from .product_series_source import source_metadata, verify_source
from .thread_products import checked_ref, _snapshot
from .product_comparison import compare_products


def product_key(ref):
    return sha256(json.dumps(checked_ref(ref), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class ProductSeriesService:
    def __init__(self, threads, objects):
        self.threads, self.objects = threads, objects
        self.store = None
        if not hasattr(threads, '_lock'):
            self.store = ProductSeriesStore(threads)
            self.store.initialize()
        elif not hasattr(threads, '_product_series'):
            threads._product_series = {}

    def _memory(self, thread_id):
        """Call only under the Thread lock after checking its access scope."""
        return self.threads._product_series.setdefault(thread_id, ({}, {}, {}, [], {}))

    def command(self, thread_id, request, *, actor):
        fields = {'schema','series_id','expected_revision','operation','product','command_id','idempotency_key'}
        if not isinstance(request, dict) or set(request) != fields or request['schema'] != 'capstone-product-series-command/1':
            raise ValueError('invalid versioned series command')
        command = {key:value for key,value in request.items() if key != 'schema'}
        def validate(connection, ref):
            reader = self._reader_for(thread_id, connection)
            verify_source(reader, self.objects, thread_id, ref)
        if self.store:
            return self.store.apply(thread_id, command, validate=validate, actor=actor)
        if not isinstance(actor, str) or not actor or len(actor)>255:
            raise ValueError('authenticated actor required')
        for key in ('series_id','command_id','idempotency_key'):
            if not isinstance(command[key],str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', command[key]):
                raise ValueError('invalid command identity')
        digest = sha256(json.dumps({'request':command,'actor':actor},sort_keys=True,allow_nan=False,separators=(',', ':')).encode()).hexdigest()
        with self.threads._lock:
            _snapshot(self.threads, thread_id)
            states, receipts, commands, events, index = self._memory(thread_id)
            old = receipts.get(command['idempotency_key'])
            if old:
                if old[0] != digest: raise ValueError('idempotency conflict')
                return deepcopy(old[1])
            if self.threads.is_archived(thread_id): raise ValueError('Thread archived')
            if command['command_id'] in commands: raise ValueError('command identity conflict')
            series = command['series_id']
            state = transition(states.get(series),thread_id=thread_id,**{k:command[k] for k in ('series_id','expected_revision','operation','product')})
            if command['product'] is not None: validate(None, command['product'])
            key = product_key(command['product']) if command['product'] is not None else None
            if command['operation']=='register' and key in index and index[key] != series:
                raise ValueError('product already belongs to another series')
            states[series] = state
            if command['operation']=='register': index[key] = series
            receipt=deepcopy(state)
            receipt['members']=sorted(receipt['members'],key=product_key)[:20]
            receipts[command['idempotency_key']] = (digest, receipt)
            commands[command['command_id']] = True
            events.append({'series_id':series,'actor':actor,'created_at':datetime.now(timezone.utc).isoformat(),
                'operation':command['operation'],'product':command['product'],'previous_revision':command['expected_revision'],
                'revision':state['revision'],'adopted_ref':state['adopted_ref']})
            return deepcopy(receipt)

    def _reader_for(self, thread_id, connection):
        if connection is None: return self.threads
        row = connection.execute('SELECT * FROM capstone_threads WHERE thread_id=%s', (thread_id,)).fetchone()
        return SimpleNamespace(_connect=lambda: nullcontext(connection),
            snapshot=lambda thread: self.threads._snapshot_from_row(row),
            _event_from_row=self.threads._event_from_row)

    def read(self, thread_id, series_id):
        if self.store: return self.store.read(thread_id, series_id)
        with self.threads._lock:
            _snapshot(self.threads,thread_id)
            state=deepcopy(self._memory(thread_id)[0][series_id])
            state['members']=sorted(state['members'],key=product_key)[:20]
            return state

    def list(self, thread_id, *, limit=20, before=None):
        if type(limit) is not int or not 1<=limit<=100: raise ValueError('invalid page')
        if self.store: return self.store.list(thread_id,limit=limit,before=before)
        with self.threads._lock:
            _snapshot(self.threads,thread_id)
            keys = sorted(k for k in self._memory(thread_id)[0] if before is None or k>before)[:limit+1]
            return {'series':[self.read(thread_id,k) for k in keys[:limit]],'next_cursor':keys[limit-1] if len(keys)>limit else None}

    def discover(self, thread_id, product):
        product=checked_ref(product)
        if product['thread_id']!=thread_id: raise ValueError('product scope mismatch')
        if self.store: return self.store.discover(thread_id,product_key(product))
        with self.threads._lock:
            _snapshot(self.threads,thread_id)
            series=self._memory(thread_id)[4].get(product_key(product))
            return {'series':self.read(thread_id,series) if series else None}

    def members(self, thread_id, series_id, *, limit=20, after=None):
        if type(limit) is not int or not 1<=limit<=100: raise ValueError('invalid page')
        if self.store: return self.store.members(thread_id,series_id,limit=limit,after=after)
        with self.threads._lock:
            _snapshot(self.threads,thread_id)
            refs=sorted(self._memory(thread_id)[0][series_id]['members'],key=product_key)
            refs=[deepcopy(r) for r in refs if after is None or product_key(r)>after][:limit+1]
            return {'members':refs[:limit],'next_cursor':product_key(refs[limit-1]) if len(refs)>limit else None}

    def history(self, thread_id, series_id, *, limit=20, before=None):
        self.read(thread_id,series_id)
        if type(limit) is not int or not 1<=limit<=100: raise ValueError('invalid page')
        if self.store: return self.store.history(thread_id,series_id,limit=limit,before=before)
        with self.threads._lock:
            _snapshot(self.threads, thread_id)
            events=[deepcopy(e) for e in reversed(self._memory(thread_id)[3]) if e['series_id']==series_id and (before is None or e['revision']<=before)][:limit+1]
            return {'events':events[:limit],'next_revision':events[limit-1]['revision']-1 if len(events)>limit else None}

    def sources(self, thread_id, product):
        metadata=source_metadata(self.threads,thread_id,product)
        attempt=metadata['ref']['producer_attempt_id'] or metadata['ref']['attempt_id']
        if self.store:
            with self.threads._connect() as c:
                row=c.execute('SELECT submission_snapshot FROM capstone_thread_attempts WHERE thread_id=%s AND attempt_id=%s',(thread_id,attempt)).fetchone()
                submission=(row or {}).get('submission_snapshot') or {}
        else:
            submission=(self.threads._attempts.get(attempt) or {}).get('submission') or {}
        return {'sources':deepcopy(submission.get('context_product_refs',[]))}

    def compare(self, thread_id, original_ref, revised_ref):
        return compare_products(self.threads,self.objects,thread_id,original_ref,revised_ref,
            max_input_bytes=256*1024,max_lines=5000,max_output_bytes=1024*1024)
