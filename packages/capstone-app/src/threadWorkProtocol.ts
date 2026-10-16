import { parseContext, parseThreadSnapshot, ThreadProtocolError, type ModelContextSnapshot, type ThreadSnapshot } from './threadProtocol'

export type WorkRecord = {
  workId: string; goal: string; goalRevision: number; revision: number; status: string
  blockedReason: string | null; messages: string[]
}
export type WorkSnapshot = {
  threadId: string; runId: string; selectedModelContextId: string | null
  modelContext: ModelContextSnapshot | null; lastEventSeq: number; baseEventSeq: number
  works: WorkRecord[]
  professionalSnapshot?: ThreadSnapshot
}
export type WorkCommand = {
  schema: 'capstone-command/2'; thread_id: string; run_id: string
  command_id: string; idempotency_key: string; kind: 'work_message' | 'revise_goal'
  target: { kind: 'work'; id: string; expected_revision: number }
  payload: { text: string }
}
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new ThreadProtocolError('工作记录无效')
  return value as Record<string, unknown>
}
function id(value: unknown): string {
  if (typeof value !== 'string' || !/^[a-z][a-z0-9_-]{0,127}$/.test(value)) throw new ThreadProtocolError('工作身份无效')
  return value
}
function revision(value: unknown, minimum = 0): number {
  if (!Number.isSafeInteger(value) || (value as number) < minimum) throw new ThreadProtocolError('工作修订无效')
  return value as number
}

export function parseWorkSnapshot(value: unknown): WorkSnapshot {
  const body = object(value)
  if (body.schema !== 'capstone-thread-snapshot/2' || body.minimum_protocol_version !== 2
      || !Array.isArray(body.works) || body.works.length > 64) throw new ThreadProtocolError('工作会话协议无效')
  const threadId = id(body.thread_id)
  const runId = id(object(body.run).run_id)
  const lastEventSeq = revision(body.last_event_seq)
  const baseEventSeq = revision(body.base_event_seq)
  if (baseEventSeq > lastEventSeq) throw new ThreadProtocolError('工作会话游标无效')
  const modelContext = body.active_model_context === null ? null : parseContext(body.active_model_context, '工作模型')
  const selectedModelContextId = body.selected_model_context_id === null ? null : id(body.selected_model_context_id)
  if ((modelContext?.id ?? null) !== selectedModelContextId) throw new ThreadProtocolError('工作模型关联无效')
  const works = body.works.map((raw): WorkRecord => {
    const work = object(raw)
    const workId = id(work.work_id)
    const context = object(work.task_context)
    const binding = object(context.binding)
    if (binding.thread_id !== threadId || binding.work_id !== workId
        || context.goal_revision !== work.goal_revision || !Array.isArray(context.model_contexts)
        || !Array.isArray(context.resource_refs)) throw new ThreadProtocolError('工作上下文关联无效')
    if (typeof work.goal !== 'string' || !work.goal.trim() || work.goal.length > 65536
        || work.status !== 'blocked' || work.blocked_reason !== 'execution_unavailable'
        || !Array.isArray(work.messages) || !work.messages.length || work.messages.length > 128
        || work.messages.some(message => typeof message !== 'string' || !message.trim())) throw new ThreadProtocolError('工作内容无效')
    if (revision(work.goal_revision, 1) > revision(work.revision, 1)) throw new ThreadProtocolError('目标修订无效')
    return { workId, goal: work.goal, goalRevision: revision(work.goal_revision, 1),
      revision: revision(work.revision, 1), status: work.status,
      blockedReason: work.blocked_reason as string | null, messages: work.messages as string[] }
  })
  if (new Set(works.map(work => work.workId)).size !== works.length) throw new ThreadProtocolError('工作身份重复')
  let professionalSnapshot: ThreadSnapshot | undefined
  if (modelContext) {
    const inherited = Object.fromEntries(Object.entries(body).filter(([key]) =>
      !['minimum_protocol_version', 'selected_model_context_id', 'task_context', 'works'].includes(key)))
    professionalSnapshot = parseThreadSnapshot({ ...inherited, schema: 'capstone-thread-snapshot/1' })
  }
  return { threadId, runId, modelContext, selectedModelContextId, lastEventSeq, baseEventSeq, works, professionalSnapshot }
}

export function buildWorkCommand(threadId: string, runId: string, commandId: string, idempotencyKey: string,
                                 workId: string, expectedRevision: number, text: string,
                                 kind: WorkCommand['kind'] = 'work_message'): WorkCommand {
  if (!text.trim() || text.length > 65536) throw new ThreadProtocolError('请输入有效任务内容')
  if (kind !== 'work_message' && kind !== 'revise_goal') throw new ThreadProtocolError('工作操作无效')
  const command: WorkCommand = { schema: 'capstone-command/2', thread_id: id(threadId), run_id: id(runId),
    command_id: id(commandId), idempotency_key: id(idempotencyKey), kind,
    target: { kind: 'work', id: id(workId), expected_revision: revision(expectedRevision) }, payload: { text } }
  if (new TextEncoder().encode(JSON.stringify(command)).byteLength > 65536) throw new ThreadProtocolError('任务内容过长，请分次补充。')
  return command
}
