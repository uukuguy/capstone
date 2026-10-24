import { parseSessionTitle, type SessionTitle } from './sessionTitle'

export type ThreadDescriptor = {
  sessionTitle?: SessionTitle
  threadId: string; modelId: string | null; implementationFamily: string | null
  minimumProtocolVersion?: number
  createdAt: string; archived: boolean; lastEventSeq: number
}
export type ThreadListPage = { threads: ThreadDescriptor[]; nextBeforeThreadId: string | null; hasMore: boolean }

export function parseThreadDescriptor(value: unknown): ThreadDescriptor {
  if (!value || typeof value !== 'object') throw new Error('会话信息无效')
  const row = value as Record<string, unknown>
  const version = row.minimum_protocol_version ?? 1
  if (version !== 1 && version !== 2) throw new Error('会话版本无效')
  for (const key of ['thread_id', 'model_id', 'implementation_family', 'created_at']) {
    if (version === 2 && (key === 'model_id' || key === 'implementation_family') && row[key] === null) continue
    if (typeof row[key] !== 'string' || !row[key] || row[key].length > 200) throw new Error('会话信息无效')
  }
  if (!/^[a-z][a-z0-9_-]{0,63}$/.test(row.thread_id as string)
      || typeof row.archived !== 'boolean' || !Number.isSafeInteger(row.last_event_seq)
      || (row.last_event_seq as number) < 0) throw new Error('会话信息无效')
  if ((row.model_id === null) !== (row.implementation_family === null)) throw new Error('会话模型关联无效')
  return { threadId: row.thread_id as string, modelId: row.model_id as string | null,
    implementationFamily: row.implementation_family as string | null, createdAt: row.created_at as string,
    ...(version === 2 ? { minimumProtocolVersion: 2 } : {}),
    ...(row.session_title == null ? {} : {sessionTitle: parseSessionTitle(row.session_title)}),
    archived: row.archived, lastEventSeq: row.last_event_seq as number }
}

export function parseThreadListPage(value: unknown): ThreadListPage {
  if (!value || typeof value !== 'object') throw new Error('会话列表无效')
  const body = value as Record<string, unknown>
  if (body.schema !== 'capstone-thread-list/1' || !Array.isArray(body.threads)
      || body.threads.length > 50 || typeof body.has_more !== 'boolean'
      || !(body.next_before_thread_id === null || typeof body.next_before_thread_id === 'string')) throw new Error('会话列表无效')
  const threads = body.threads.map(parseThreadDescriptor)
  if (body.has_more && (!threads.length || body.next_before_thread_id !== threads.at(-1)?.threadId)) throw new Error('会话列表游标无效')
  return { threads, nextBeforeThreadId: body.next_before_thread_id as string | null, hasMore: body.has_more }
}
