"""Rebuildable resource read model. Durable Thread events remain authoritative."""
from psycopg.types.json import Jsonb

SCHEMA = """
CREATE INDEX IF NOT EXISTS capstone_resource_events_revision_idx
    ON capstone_thread_events (thread_id,event_seq DESC)
    WHERE event_type IN ('resource_upload_started','resource_part_reserved','resource_part_stored','resource_upload_cancelled','resource_published','command_accepted');
CREATE TABLE IF NOT EXISTS capstone_resource_projection_cursors (
    thread_id text PRIMARY KEY REFERENCES capstone_threads(thread_id) ON DELETE CASCADE,
    event_seq integer NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS capstone_resource_uploads (
    thread_id text NOT NULL REFERENCES capstone_resource_projection_cursors(thread_id) ON DELETE CASCADE,
    upload_id text NOT NULL,
    metadata jsonb NOT NULL,
    published_seq integer,
    PRIMARY KEY (thread_id, upload_id)
);
CREATE TABLE IF NOT EXISTS capstone_resource_parts (
    thread_id text NOT NULL,
    upload_id text NOT NULL,
    part_index integer NOT NULL,
    metadata jsonb NOT NULL,
    stored boolean NOT NULL DEFAULT false,
    PRIMARY KEY (thread_id, upload_id, part_index),
    FOREIGN KEY (thread_id, upload_id) REFERENCES capstone_resource_uploads(thread_id, upload_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS capstone_resource_uploads_page_idx
    ON capstone_resource_uploads (thread_id,published_seq) WHERE published_seq IS NOT NULL;
"""


def synchronize(connection, thread):
    """Advance in Thread-then-cursor lock order, with no object storage I/O.

    Callers already mutating a Thread keep their existing transaction. Readers
    use the same lock order, including foreign-key checks on first creation.
    Cursor and rows commit together, including recovery from old event-only data.
    """
    row = connection.execute('SELECT thread_id FROM capstone_threads WHERE thread_id=%s FOR UPDATE', (thread,)).fetchone()
    if row is None:
        raise ValueError('upload not found in this session')
    connection.execute('INSERT INTO capstone_resource_projection_cursors (thread_id) VALUES (%s) ON CONFLICT DO NOTHING', (thread,))
    cursor = connection.execute('SELECT event_seq FROM capstone_resource_projection_cursors WHERE thread_id=%s FOR UPDATE', (thread,)).fetchone()['event_seq']
    while True:
        events = connection.execute('SELECT event_seq,event_type,payload FROM capstone_thread_events WHERE thread_id=%s AND event_seq>%s ORDER BY event_seq LIMIT 256', (thread, cursor)).fetchall()
        if not events:
            return
        for event in events:
            _apply(connection, thread, event)
        cursor = events[-1]['event_seq']
        connection.execute('UPDATE capstone_resource_projection_cursors SET event_seq=%s WHERE thread_id=%s', (cursor, thread))


def _apply(connection, thread, event):
    kind, p = event['event_type'], event['payload']
    uid = p.get('upload_id')
    if kind == 'resource_upload_started':
        connection.execute('INSERT INTO capstone_resource_uploads (thread_id,upload_id,metadata) VALUES (%s,%s,%s)',
                           (thread, uid, Jsonb({**p, 'initial_draft': p.get('draft', False), 'state': 'uploading'})))
    elif kind in ('resource_part_reserved', 'resource_part_stored'):
        connection.execute('''INSERT INTO capstone_resource_parts (thread_id,upload_id,part_index,metadata,stored)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT (thread_id,upload_id,part_index)
            DO UPDATE SET stored=capstone_resource_parts.stored OR EXCLUDED.stored''',
            (thread, uid, p['index'], Jsonb(p), kind == 'resource_part_stored'))
    elif kind == 'resource_upload_cancelled':
        connection.execute('UPDATE capstone_resource_uploads SET metadata=metadata || %s WHERE thread_id=%s AND upload_id=%s',
                           (Jsonb({'state': p['state']}), thread, uid))
    elif kind == 'resource_published':
        connection.execute('UPDATE capstone_resource_uploads SET metadata=metadata || %s,published_seq=%s WHERE thread_id=%s AND upload_id=%s',
                           (Jsonb({'state': 'complete', 'resource': p['resource']}), event['event_seq'], thread, uid))
    elif kind == 'command_accepted':
        for ref in p.get('attachment_refs', []):
            connection.execute('UPDATE capstone_resource_uploads SET metadata=metadata || %s WHERE thread_id=%s AND upload_id=%s',
                               (Jsonb({'draft': False}), thread, 'upload_' + ref.removeprefix('resource_')))


def state(connection, thread, uid, *, part_index=None, include_parts=True):
    synchronize(connection, thread)
    row = connection.execute('SELECT metadata FROM capstone_resource_uploads WHERE thread_id=%s AND upload_id=%s', (thread, uid)).fetchone()
    if row is None:
        raise ValueError('upload not found in this session')
    result = {**row['metadata'], 'parts': {}, 'reserved': {}}
    if include_parts:
        query = 'SELECT metadata,stored FROM capstone_resource_parts WHERE thread_id=%s AND upload_id=%s'
        args = (thread, uid)
        if part_index is not None:
            query += ' AND part_index=%s'
            args += (part_index,)
        for part in connection.execute(query, args):
            p = part['metadata']
            result['reserved'][p['index']] = p
            if part['stored']:
                result['parts'][p['index']] = p
    return result


def states(connection, thread, *, published_only=True):
    synchronize(connection, thread)
    query = 'SELECT metadata FROM capstone_resource_uploads WHERE thread_id=%s'
    if published_only:
        query += ' AND published_seq IS NOT NULL'
    query += ' ORDER BY published_seq NULLS LAST,upload_id'
    return [row['metadata'] for row in connection.execute(query, (thread,))]


def page(connection, thread, draft, after, limit):
    synchronize(connection, thread)
    revision = connection.execute("""SELECT COALESCE(MAX(event_seq),0) AS revision FROM capstone_thread_events
        WHERE thread_id=%s AND event_type IN ('resource_upload_started','resource_part_reserved','resource_part_stored',
        'resource_upload_cancelled','resource_published','command_accepted')""", (thread,)).fetchone()['revision']
    rows = connection.execute("""SELECT metadata,published_seq FROM capstone_resource_uploads
        WHERE thread_id=%s AND published_seq>%s AND metadata->>'state'='complete'
        AND COALESCE((metadata->>'draft')::boolean,false)=%s
        ORDER BY published_seq LIMIT %s""", (thread, after, draft, limit+1)).fetchall()
    return revision, [(row['published_seq'], row['metadata']['resource']) for row in rows]
