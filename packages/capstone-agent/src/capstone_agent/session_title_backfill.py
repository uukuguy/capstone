"""Persist deterministic names from completed ledger sources, without a model call.

This is a naming projection. It does not change Work goals, execution identity,
protocol versions, or the completion status of a delivery.
"""
from dataclasses import replace
from datetime import datetime, timezone
from collections.abc import Mapping
import re
import secrets

from psycopg.types.json import Jsonb

from .session_title import SessionTitle
from .thread_protocol import EventEnvelope


def _focus(value):
    if not isinstance(value, str):
        return None
    text = ' '.join(''.join(char if ord(char) >= 32 else ' ' for char in value).split())
    # Conversational continuations and edits refer to an existing subject.
    # They provide no evidence of a new session topic.
    if re.match(r'^(?:谢谢|感谢|继续|请继续|只把|只改|仅修改|保持|thanks?\b|thank you\b|continue\b)', text, re.I):
        return None
    if re.search(r'(?:上一版|上一个|刚才的|previous (?:report|version|answer))', text, re.I):
        return None
    plain = re.sub(r'[\W_]+', '', text).casefold()
    if len(plain) < 4 or plain in {
        '谢谢你的帮助', '谢谢你的回答', '继续执行', '请继续执行', '继续分析', '好的继续',
        'thankyou', 'thanks', 'continue', 'pleasecontinue', 'okcontinue',
    }:
        return None
    return '会话主题' if len(text) > 32 else text


def _candidate(kind, payload, attempt_id, seq):
    if kind == 'session_title_summary':
        title = payload.get('title')
        if payload.get('status') == 'completed' and isinstance(title, str) and 0 < len(title) <= 64:
            return title, 'summary:'+payload['attempt_id'], payload.get('work_id'), kind
        return None
    if kind == 'delivery_published':
        delivery = payload.get('delivery', {})
        if not isinstance(delivery, Mapping):
            return None
        if delivery.get('generation_status') != 'completed':
            return None
        title = delivery.get('title')
        artifact = delivery.get('artifact_id')
        revision = delivery.get('revision')
        if isinstance(title, str) and title.strip() and isinstance(artifact, str) and type(revision) is int:
            text = ' '.join(''.join(char if ord(char) >= 32 else ' ' for char in title).split())
            if text:
                return text[:160], f'{artifact}:{revision}', delivery.get('work_id'), kind
    elif kind == 'attempt_completed':
        title = _focus(payload.get('text'))
        if title and isinstance(attempt_id, str):
            return title, f'completed:{attempt_id}:{seq}', payload.get('work_id'), kind
    return None


def _select_source(candidates):
    latest_input = None
    for candidate in candidates:
        if candidate is None:
            continue
        if candidate[3] == 'session_title_summary':
            return (latest_input or candidate)[:2]
        if candidate[3] == 'delivery_published':
            # A task delivery remains the task name through follow-up instructions.
            # Only an explicitly different Work proves a newer task. Unknown
            # ownership is not a license to demote the accepted task delivery.
            chosen = latest_input if (latest_input and isinstance(latest_input[2], str)
                and latest_input[2] != candidate[2]) else candidate
            return chosen[:2]
        if latest_input is None:
            latest_input = candidate
    return None if latest_input is None else latest_input[:2]


def _memory_source(events):
    accepted = {event.attempt_id: {'text': event.payload.get('payload', {}).get('text'),
                                 'work_id': event.payload.get('work_id')}
                for event in events if event.event_type == 'command_accepted'}
    return _select_source(_candidate(event.event_type,
        accepted.get(event.attempt_id, {}) if event.event_type == 'attempt_completed' else event.payload,
        event.attempt_id, event.event_seq) for event in reversed(events))


def _postgres_source(connection, thread_id):
    # Use durable events, never the bounded public history window. Stream candidates
    # newest first so long sessions do not need a full history document in memory.
    with connection.cursor(name='title_sources_' + secrets.token_hex(6)) as cursor:
        cursor.execute('''
        SELECT e.event_type,e.event_seq,e.attempt_id,
          CASE WHEN e.event_type='attempt_completed' THEN
            (SELECT jsonb_build_object('text', a.payload->'payload'->>'text', 'work_id', a.payload->>'work_id')
              FROM capstone_thread_events a WHERE a.thread_id=e.thread_id
                AND a.attempt_id=e.attempt_id AND a.event_type='command_accepted'
              ORDER BY a.event_seq DESC LIMIT 1) ELSE e.payload END AS payload
        FROM capstone_thread_events e WHERE e.thread_id=%s
          AND e.event_type IN ('attempt_completed','delivery_published','session_title_summary')
        ORDER BY e.event_seq DESC''', (thread_id,))
        return _select_source(_candidate(row['event_type'], row['payload'] or {}, row['attempt_id'], row['event_seq'])
                              for row in cursor)


def _busy(snapshot):
    execution = (snapshot.application_state or {}).get('case_execution', {})
    return snapshot.current_attempt is not None or (isinstance(execution, Mapping)
        and execution.get('status') in {'created', 'running', 'waiting_step', 'blocked'})


def _title(snapshot, created_at, source):
    current = snapshot.session_title
    if current is not None and current.source == 'user':
        return current
    if current is None:
        names = {'grid-analysis': '电网分析与决策', 'enterprise-research': '企业研究与分析', 'general-chat': '通用聊天'}
        current = SessionTitle(names.get(snapshot.session_type,
            '电网分析与决策' if snapshot.active_model_context is not None else '历史会话'))
    if source:
        return current.suggest(source[0], expected_revision=current.revision, source_ref=source[1])
    if current.source == 'default' and ' · ' not in current.text:
        instant = datetime.fromisoformat(created_at) if isinstance(created_at, str) else created_at
        stamp = instant.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
        return replace(current, text=f'{current.text[:135]} · {stamp}')
    return current


def ensure_session_title(service, thread_id):
    """Backfill at a public read boundary; nested mutation reads must stay pure.

    Return the saved snapshot when acquired, else None. SKIP LOCKED is deliberate:
    artifact readers can call snapshot while the same Thread is being committed.
    """
    if hasattr(service, '_lock'):
        if service._lock._is_owned():
            return None
        with service._lock:
            service._check_thread(thread_id)
            snapshot = service._snapshot
            if _busy(snapshot) or (snapshot.session_title and snapshot.session_title.source == 'user'):
                return snapshot
            title = _title(snapshot, service._created_at, _memory_source(service._events))
            if title != snapshot.session_title:
                seq = snapshot.last_event_seq
                if title.source == 'automatic':
                    event = service._append_control_event(event_type='session_title_changed', payload={
                        'session_title': title.to_document(), 'naming_method': 'completed_topic_source'})
                    seq = event.event_seq
                service._snapshot = replace(snapshot, session_title=title, last_event_seq=seq)
            return service._snapshot
    with service._connect() as connection:
        row = connection.execute('SELECT * FROM capstone_threads WHERE thread_id=%s FOR UPDATE SKIP LOCKED', (thread_id,)).fetchone()
        if row is None:
            return None
        snapshot = service._snapshot_from_row(row)
        if _busy(snapshot) or (snapshot.session_title and snapshot.session_title.source == 'user'):
            return snapshot
        title = _title(snapshot, row['created_at'], _postgres_source(connection, thread_id))
        if title != snapshot.session_title:
            seq = snapshot.last_event_seq
            if title.source == 'automatic':
                seq += 1
                event = EventEnvelope('evt_' + secrets.token_hex(8), seq, 'session_title_changed', 1,
                    thread_id, snapshot.run.run_id, None, None, None, None,
                    datetime.now(timezone.utc).isoformat(), 'public', {
                        'session_title': title.to_document(), 'naming_method': 'completed_topic_source'})
                service._insert_event(connection, event)
            connection.execute('UPDATE capstone_threads SET session_title=%s,last_event_seq=%s WHERE thread_id=%s',
                               (Jsonb(title.to_document()), seq, thread_id))
            snapshot = replace(snapshot, session_title=title, last_event_seq=seq)
        return snapshot
