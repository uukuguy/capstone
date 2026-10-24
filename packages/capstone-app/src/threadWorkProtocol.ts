import { parseContext, parseThreadSnapshot, ThreadProtocolError, type ModelContextSnapshot, type ThreadSnapshot } from './threadProtocol'
import { parseSessionTitle, type SessionTitle } from './sessionTitle'

export type WorkRecord = {
  workId: string; goal: string; goalRevision: number; revision: number; status: string
  blockedReason: string | null; messages: string[]
  latestAttemptId: string | null; startAvailable: boolean; startUnavailableReason: string | null
  cancelRequested?: boolean
}
export type WorkSnapshot = {
  sessionTitle?: SessionTitle
  threadId: string; runId: string; selectedModelContextId: string | null
  modelContext: ModelContextSnapshot | null; lastEventSeq: number; baseEventSeq: number
  works: WorkRecord[]
  professionalSnapshot?: ThreadSnapshot
  toDocument: () => Record<string, unknown>
}
export type WorkCommand = {
  schema: 'capstone-command/2'; thread_id: string; run_id: string
  command_id: string; idempotency_key: string; kind: 'work_message' | 'revise_goal' | 'start_work' | 'cancel_work'
  target: { kind: 'work'; id: string; expected_revision: number }
  payload: { text: string } | Record<string, never>
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
        || !['ready', 'queued', 'running', 'completed', 'failed', 'cancelled', 'interrupted', 'blocked'].includes(String(work.status))
        || !(work.blocked_reason === null || typeof work.blocked_reason === 'string')
        || !Array.isArray(work.messages) || !work.messages.length || work.messages.length > 128
        || work.messages.some(message => typeof message !== 'string' || !message.trim())) throw new ThreadProtocolError('工作内容无效')
    if (revision(work.goal_revision, 1) > revision(work.revision, 1)) throw new ThreadProtocolError('目标修订无效')
    if ((work.start_available !== undefined && typeof work.start_available !== 'boolean')
        || (work.cancel_requested !== undefined && typeof work.cancel_requested !== 'boolean')
        || (work.start_unavailable_reason != null && (typeof work.start_unavailable_reason !== 'string' || work.start_unavailable_reason.length > 200))) throw new ThreadProtocolError('工作操作状态无效')
    return { workId, goal: work.goal, goalRevision: revision(work.goal_revision, 1),
      revision: revision(work.revision, 1), status: work.status as string,
      latestAttemptId: work.latest_attempt_id == null ? null : id(work.latest_attempt_id),
      startAvailable: typeof work.start_available === 'boolean' ? work.start_available : false,
      cancelRequested: work.cancel_requested === true,
      startUnavailableReason: work.start_unavailable_reason == null ? null : String(work.start_unavailable_reason),
      blockedReason: work.blocked_reason as string | null, messages: work.messages as string[] }
  })
  if (new Set(works.map(work => work.workId)).size !== works.length) throw new ThreadProtocolError('工作身份重复')
  let professionalSnapshot: ThreadSnapshot | undefined
  if (modelContext) {
    const inherited = Object.fromEntries(Object.entries(body).filter(([key]) =>
      !['minimum_protocol_version', 'selected_model_context_id', 'task_context', 'works'].includes(key)))
    professionalSnapshot = parseThreadSnapshot({ ...inherited, schema: 'capstone-thread-snapshot/1' })
  }
  return { threadId, runId, modelContext, selectedModelContextId, lastEventSeq, baseEventSeq, works, professionalSnapshot,
    ...(body.session_title == null ? {} : {sessionTitle: parseSessionTitle(body.session_title)}),
    toDocument: () => structuredClone(body) }
}

export function buildWorkCommand(threadId: string, runId: string, commandId: string, idempotencyKey: string,
                                 workId: string, expectedRevision: number, text: string,
                                 kind: 'work_message' | 'revise_goal' = 'work_message'): WorkCommand {
  if (!text.trim() || text.length > 65536) throw new ThreadProtocolError('请输入有效任务内容')
  if (kind !== 'work_message' && kind !== 'revise_goal') throw new ThreadProtocolError('工作操作无效')
  const command: WorkCommand = { schema: 'capstone-command/2', thread_id: id(threadId), run_id: id(runId),
    command_id: id(commandId), idempotency_key: id(idempotencyKey), kind,
    target: { kind: 'work', id: id(workId), expected_revision: revision(expectedRevision) }, payload: { text } }
  if (new TextEncoder().encode(JSON.stringify(command)).byteLength > 65536) throw new ThreadProtocolError('任务内容过长，请分次补充。')
  return command
}

export function buildStartWorkCommand(threadId: string, runId: string, commandId: string, idempotencyKey: string,
                                      workId: string, expectedRevision: number): WorkCommand {
  if (workId === 'new' || expectedRevision < 1) throw new ThreadProtocolError('请先保存任务目标')
  return { schema: 'capstone-command/2', thread_id: id(threadId), run_id: id(runId), command_id: id(commandId),
    idempotency_key: id(idempotencyKey), kind: 'start_work', target: { kind: 'work', id: id(workId), expected_revision: revision(expectedRevision, 1) }, payload: {} }
}

export function buildCancelWorkCommand(threadId: string, runId: string, commandId: string, idempotencyKey: string,
                                       workId: string, expectedRevision: number): WorkCommand {
  return { ...buildStartWorkCommand(threadId, runId, commandId, idempotencyKey, workId, expectedRevision), kind: 'cancel_work' }
}

export function parseStoredWorkCommand(value: unknown, threadId: string): WorkCommand {
  const command = object(value)
  const target = object(command.target)
  const payload = object(command.payload)
  if (command.schema !== 'capstone-command/2' || command.thread_id !== threadId || target.kind !== 'work') throw new ThreadProtocolError('工作命令身份无效')
  if (command.kind === 'start_work' && Object.keys(payload).length === 0) return buildStartWorkCommand(threadId, id(command.run_id), id(command.command_id), id(command.idempotency_key), id(target.id), revision(target.expected_revision))
  if (command.kind === 'cancel_work' && Object.keys(payload).length === 0) return buildCancelWorkCommand(threadId, id(command.run_id), id(command.command_id), id(command.idempotency_key), id(target.id), revision(target.expected_revision))
  if ((command.kind === 'work_message' || command.kind === 'revise_goal') && typeof payload.text === 'string' && Object.keys(payload).length === 1) return buildWorkCommand(threadId, id(command.run_id), id(command.command_id), id(command.idempotency_key), id(target.id), revision(target.expected_revision), payload.text, command.kind)
  throw new ThreadProtocolError('工作命令无效')
}
