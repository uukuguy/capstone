"""Bounded provisional Thinking transport and required durable write barrier."""
from __future__ import annotations

import json
import threading
import time
import uuid
import urllib.request
from datetime import datetime, timezone
from collections import OrderedDict

PREVIEW_METADATA = frozenset({'task_id', 'task_step_id', 'task_step_number', 'runtime_mode',
                              'step_id', 'trace_correlation_id', 'trace_sequence', 'correlation_id'})


class PreviewBus:
    def __init__(self, max_batches=256, ttl=30):
        self.rows = OrderedDict()
        self.lock = threading.Lock()
        self.max_batches, self.ttl = max_batches, ttl

    def publish(self, payload, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            self.rows[payload['batch_id']] = (now, dict(payload))
            while len(self.rows) > self.max_batches:
                self.rows.popitem(last=False)

    def read(self, thread_id, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            for key, (stamp, _) in list(self.rows.items()):
                if now - stamp > self.ttl:
                    del self.rows[key]
            return [dict(row) for _, row in self.rows.values() if row['thread_id'] == thread_id]

    def discard(self, ids):
        with self.lock:
            for key in ids:
                self.rows.pop(key, None)


def http_publisher(origin, token, claim):
    def publish(payload):
        body = {**payload, 'thread_id': claim.thread_id,
                'attempt_id': claim.attempt.attempt_id,
                'workspace_name': claim.workspace_name, 'lease_token': claim.lease_token}
        request = urllib.request.Request(origin.rstrip('/') + '/internal/thinking-preview',
            data=json.dumps(body, ensure_ascii=False).encode(), headers={'Content-Type': 'application/json',
                                                    'Authorization': 'Bearer ' + token})
        try:
            with urllib.request.urlopen(request, timeout=0.2) as response:
                response.read(1024)
        except Exception:
            pass  # Preview loss does not weaken required persistence.
    return publish


class ThinkingWriter:
    def __init__(self, service, claim, publish, interval=5, max_chars=16384):
        self.service, self.claim, self.publish = service, claim, publish
        self.interval, self.max_chars = interval, max_chars
        self.condition = threading.Condition()
        self.pending = []
        self.chars = 0
        self.busy = self.stopped = self.force = False
        self.error = None
        self.in_flight = self.flushers = 0
        self.reserved_bytes = 0
        self.thread = threading.Thread(target=self._run, daemon=True, name='thinking-durable-writer')
        self.thread.start()

    def __getattr__(self, name):
        return getattr(self.service, name)

    def append_thinking(self, claim, payload, visibility='public'):
        text = payload['text']
        if not isinstance(text, str) or not text or len(text.encode('utf-8')) > self.max_chars:
            raise ValueError('Thinking batch is invalid')
        batch = uuid.uuid4().hex
        with self.condition:
            while (self.chars + self.reserved_bytes + len(text.encode('utf-8')) > self.max_chars or len(self.pending) + self.in_flight >= 64) and not self.error:
                self.force = True
                self.condition.notify_all()
                self.condition.wait()
            if self.error:
                raise self.error
            if self.stopped:
                raise RuntimeError('Thinking writer is closed')
            self.in_flight += 1
            self.reserved_bytes += len(text.encode('utf-8'))
        if visibility == 'public':
            try:
                self.publish({'batch_id': batch, 'text': text,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'payload': {key: value for key, value in payload.items() if key in PREVIEW_METADATA}})
            except Exception:
                pass
        with self.condition:
            self.in_flight -= 1
            self.reserved_bytes -= len(text.encode('utf-8'))
            if self.error:
                self.condition.notify_all()
                raise self.error
            self.pending.append((dict(payload), visibility, batch))
            self.chars += len(text.encode('utf-8'))
            if self.flushers:
                self.force = True
            self.condition.notify_all()

    def _run(self):
        deadline = time.monotonic() + self.interval
        while True:
            with self.condition:
                while not self.stopped and not self.force and time.monotonic() < deadline:
                    self.condition.wait(max(0, deadline - time.monotonic()))
                if self.stopped and not self.pending:
                    return
                rows, self.pending = self.pending, []
                self.chars = 0
                self.busy = bool(rows)
                self.force = False
                self.condition.notify_all()
            try:
                groups = []
                for payload, visibility, batch in rows:
                    metadata = {k: v for k, v in payload.items() if k != 'text'}
                    if groups and groups[-1][0] == metadata and groups[-1][1] == visibility:
                        groups[-1][2] += payload['text']
                        groups[-1][3].append(batch)
                    else:
                        groups.append([metadata, visibility, payload['text'], [batch]])
                for metadata, visibility, text, ids in groups:
                    self.service.append_runtime_event(self.claim, event_type='assistant_thinking_delta',
                        payload={**metadata, 'text': text, 'preview_batch_ids': ids}, visibility=visibility)
            except Exception as error:
                with self.condition:
                    self.error = error
                    self.stopped = True
                    self.pending = []
                    self.chars = 0
            finally:
                with self.condition:
                    self.busy = False
                    self.condition.notify_all()
            deadline = time.monotonic() + self.interval

    def flush(self):
        with self.condition:
            self.flushers += 1
            try:
                self.force = True
                self.condition.notify_all()
                while (self.pending or self.busy or self.in_flight) and not self.error:
                    self.condition.wait()
                if self.error:
                    raise self.error
            finally:
                self.flushers -= 1

    def append_runtime_event(self, *args, **kwargs):
        self.flush()
        return self.service.append_runtime_event(*args, **kwargs)

    def finish_attempt(self, *args, **kwargs):
        self.flush()
        return self.service.finish_attempt(*args, **kwargs)

    def release_attempt_for_domain(self, *args, **kwargs):
        self.flush()
        return self.service.release_attempt_for_domain(*args, **kwargs)

    def close(self):
        try:
            self.flush()
        finally:
            with self.condition:
                self.stopped = True
                self.condition.notify_all()
            self.thread.join()
