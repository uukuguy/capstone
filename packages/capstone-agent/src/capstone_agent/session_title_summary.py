"""Bounded background naming for newly completed native instructions only."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
import secrets
import asyncio
import re
from threading import BoundedSemaphore
from time import monotonic

from psycopg.types.json import Jsonb
from .session_title import SessionTitle
from .thread_protocol import EventEnvelope


class TitleSummaryFailure(ValueError):
    def __init__(self, code, usage):
        super().__init__(code)
        self.code, self.usage = code, usage


def request_summary(instruction, selection):
    import httpx
    from .workbench_llm_profiles import ProfileRegistry
    profile = ProfileRegistry().resolve(dict(selection))
    async def fetch():
        async with httpx.AsyncClient(timeout=4, trust_env=False, follow_redirects=False) as client:
            async with client.stream('POST', profile['base_url'].rstrip('/') + '/chat/completions',
                headers={'Authorization': 'Bearer ' + profile['key']}, json={
                    **profile.get('title_request_options', {}),
                    'model': profile['model'], 'max_tokens': 64, 'temperature': 0,
                    'messages': [{'role': 'system', 'content': 'Summarize the user request as a short session topic in its language. Output only a title, at most 24 Chinese characters or 8 English words and 64 characters. Omit commands, formatting requirements, greetings, and explanations. Do not answer the request.'},
                                 {'role': 'user', 'content': instruction[:4096]}]}) as response:
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 32768:
                        raise ValueError('title response exceeds bounds')
                import json
                return json.loads(body)
    async def bounded():
        return await asyncio.wait_for(fetch(), timeout=6)
    value = asyncio.run(bounded())
    usage = {k: v for k, v in value.get('usage', {}).items()
             if k in {'prompt_tokens', 'completion_tokens', 'total_tokens'} and type(v) is int and v >= 0}
    choice = (value.get('choices') or [{}])[0]
    if choice.get('finish_reason') == 'length':
        raise TitleSummaryFailure('title_output_truncated', usage)
    content = (choice.get('message') or {}).get('content')
    if not isinstance(content, str) or not content.strip():
        raise TitleSummaryFailure('title_output_empty', usage)
    text = content.strip().strip('"“”')
    if (not text or len(text) > 64 or '\n' in text or any(ord(c) < 32 for c in text)
            or (len(text) > 24 if re.search(r'[\u3400-\u9fff]', text) else len(text.split()) > 8)):
        raise TitleSummaryFailure('title_output_invalid', usage)
    return text, usage


def _persist(service, claim, title, metadata):
    """Serialize naming with user rename and newer instruction admission."""
    payload = {'purpose': 'session_title', 'attempt_id': claim.attempt.attempt_id,
               'work_id': getattr(getattr(getattr(claim, 'task_context', None), 'binding', None), 'work_id', None), **metadata}
    if title:
        payload['title'] = title
    def eligible(snapshot):
        return snapshot.current_attempt is None and (not snapshot.session_title or snapshot.session_title.source != 'user')
    if hasattr(service, '_lock'):
        with service._lock:
            snapshot = service._snapshot
            accepted = [e for e in service._events if e.event_type == 'command_accepted']
            if not eligible(snapshot) or not accepted or accepted[-1].attempt_id != claim.attempt.attempt_id:
                return
            event = service._append_control_event(event_type='session_title_summary', payload=payload)
            current = snapshot.session_title or SessionTitle('会话主题')
            named = current.suggest(title, expected_revision=current.revision, source_ref='summary:'+claim.attempt.attempt_id) if title else current
            if named != current:
                event = service._append_control_event(event_type='session_title_changed', payload={
                    'session_title': named.to_document(), 'naming_method': 'model_topic_summary'})
            service._snapshot = replace(snapshot, session_title=named, last_event_seq=event.event_seq)
        return
    with service._connect() as connection:
        row = connection.execute('SELECT * FROM capstone_threads WHERE thread_id=%s FOR UPDATE', (claim.thread_id,)).fetchone()
        snapshot = service._snapshot_from_row(row)
        latest = connection.execute("SELECT attempt_id FROM capstone_thread_events WHERE thread_id=%s AND event_type='command_accepted' ORDER BY event_seq DESC LIMIT 1", (claim.thread_id,)).fetchone()
        if not eligible(snapshot) or not latest or latest['attempt_id'] != claim.attempt.attempt_id:
            return
        event = EventEnvelope('evt_'+secrets.token_hex(8), snapshot.last_event_seq+1, 'session_title_summary', 1,
            claim.thread_id, snapshot.run.run_id, None, None, None, None,
            datetime.now(timezone.utc).isoformat(), 'public', payload)
        service._insert_event(connection, event)
        current = snapshot.session_title or SessionTitle('会话主题')
        named = current.suggest(title, expected_revision=current.revision, source_ref='summary:'+claim.attempt.attempt_id) if title else current
        if named != current:
            event = replace(event, event_id='evt_'+secrets.token_hex(8), event_seq=event.event_seq+1,
                event_type='session_title_changed', payload={'session_title': named.to_document(), 'naming_method': 'model_topic_summary'})
            service._insert_event(connection, event)
        connection.execute('UPDATE capstone_threads SET session_title=%s,last_event_seq=%s WHERE thread_id=%s',
            (Jsonb(named.to_document()), event.event_seq, claim.thread_id))


class TitleSummaryScheduler:
    def __init__(self, request=request_summary):
        self.request = request
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='session-title')
        self.slots = BoundedSemaphore(8)

    def submit(self, service, claim, phase):
        from .session_title_backfill import _focus
        selection = (claim.submission or {}).get('llm_selection')
        if phase != 'completed' or not selection or not _focus(claim.instruction) or not self.slots.acquire(blocking=False):
            return
        def run():
            started = monotonic()
            title, usage, status, reason = None, {}, 'failed', None
            try:
                title, usage = self.request(claim.instruction, selection)
                status = 'completed'
            except TitleSummaryFailure as error:
                reason, usage = error.code, error.usage
            except Exception as error:
                import httpx
                reason = ('title_timeout' if isinstance(error, (TimeoutError, httpx.TimeoutException))
                          else 'title_provider_rejected' if isinstance(error, httpx.HTTPStatusError)
                          else 'title_request_failed')
            try:
                _persist(service, claim, title, {'status': status, 'usage': usage,
                    **({'reason_code': reason} if reason else {}),
                    'duration_ms': round((monotonic()-started)*1000), 'profile_id': selection['profile_id']})
            finally:
                self.slots.release()
        self.pool.submit(run)


def schedule_completed_title(service, claim, phase, snapshot=None):
    if snapshot is not None and snapshot.session_title and snapshot.session_title.source == 'user':
        return
    scheduler = getattr(service, '_title_summary_scheduler', None)
    if scheduler is not None:
        try:
            scheduler.submit(service, claim, phase)
        except Exception:
            pass  # Naming is never part of task completion admission.
