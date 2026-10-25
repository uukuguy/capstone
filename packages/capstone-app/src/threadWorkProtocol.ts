import {assertCapacity,exceedsCapacity} from './applicationCapacity'
import { parseContext, parseThreadSnapshot, ThreadProtocolError, type ModelContextSnapshot, type ThreadSnapshot } from './threadProtocol'
import { parseSessionTitle, type SessionTitle } from './sessionTitle'
import type { InputSubmission } from './threadInput'
import {parseContextProductRefs} from './threadProducts'
import type { AttemptPhase, RuntimeMode } from './threadProtocol'

export type WorkRecord = {
  workId: string; goal: string; goalRevision: number; revision: number; status: string
  blockedReason: string | null; messages: string[]
  latestAttemptId: string | null; startAvailable: boolean; startUnavailableReason: string | null
  cancelRequested?: boolean
  conversationMode?: boolean
}
export type WorkAttempt = { turnId: string; attemptId: string; phase: AttemptPhase;
  targetModelContextId: string | null; runtimeMode: RuntimeMode; workId: string | null }
export type WorkSnapshot = {
  sessionTitle?: SessionTitle
  sessionType?: 'general-chat' | 'enterprise-research' | 'grid-analysis'
  runtimeMode: RuntimeMode
  nativeExecution?: { available: boolean; unavailableReason: string | null }
  currentAttempt: WorkAttempt | null
  threadId: string; runId: string; selectedModelContextId: string | null
  modelContext: ModelContextSnapshot | null; lastEventSeq: number; baseEventSeq: number
  works: WorkRecord[]
  professionalSnapshot?: ThreadSnapshot
  toDocument: () => Record<string, unknown>
}
export type WorkCommand = {
  schema: 'capstone-command/2'; thread_id: string; run_id: string
  command_id: string; idempotency_key: string; kind: 'work_message' | 'revise_goal' | 'start_work' | 'cancel_work' | 'send_message' | 'open_model' | 'activate_model' | 'close_model'
  target: { kind: 'work' | 'model_workspace'; id: string; expected_revision: number }
  payload: ({ text: string; source_attempt_id?: string } & Partial<InputSubmission>) | Record<string, string>
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
function parseRuntime(value: unknown): RuntimeMode {
  if (value === undefined || value === 'capstone') return 'capstone'
  if (value === 'pi_reference') return value
  throw new ThreadProtocolError('工作运行模式无效')
}

export function parseWorkSnapshot(value: unknown): WorkSnapshot {
  const body = object(value)
  if (body.schema !== 'capstone-thread-snapshot/2' || body.minimum_protocol_version !== 2
      || !Array.isArray(body.works) || exceedsCapacity(body.works.length,'work_count')) throw new ThreadProtocolError('工作会话协议无效')
  const threadId = id(body.thread_id)
  const runId = id(object(body.run).run_id)
  const lastEventSeq = revision(body.last_event_seq)
  const baseEventSeq = revision(body.base_event_seq)
  if (baseEventSeq > lastEventSeq) throw new ThreadProtocolError('工作会话游标无效')
  const modelContext = body.active_model_context === null ? null : parseContext(body.active_model_context, '工作模型')
  const selectedModelContextId = body.selected_model_context_id === null ? null : id(body.selected_model_context_id)
  if ((modelContext?.id ?? null) !== selectedModelContextId) throw new ThreadProtocolError('工作模型关联无效')
  const runtimeMode = parseRuntime(body.runtime_mode)
  let currentAttempt: WorkAttempt | null = null
  if (body.current_attempt !== null) {
    const attempt = object(body.current_attempt)
    if (!['created', 'accepted', 'running', 'waiting', 'committing', 'cancelled', 'interrupted', 'completed', 'failed'].includes(String(attempt.phase))) throw new ThreadProtocolError('工作执行状态无效')
    const targetModelContextId = attempt.target_model_context_id === null ? null : id(attempt.target_model_context_id)
    if (targetModelContextId !== (modelContext?.id ?? null)) throw new ThreadProtocolError('工作执行模型关联无效')
    currentAttempt = {turnId: id(attempt.turn_id), attemptId: id(attempt.attempt_id), phase: attempt.phase as AttemptPhase,
      targetModelContextId, runtimeMode: parseRuntime(attempt.runtime_mode), workId: attempt.work_id == null ? null : id(attempt.work_id)}
  }
  if (body.session_type != null && !['general-chat', 'enterprise-research', 'grid-analysis'].includes(String(body.session_type))) throw new ThreadProtocolError('会话类型无效')
  let nativeExecution: WorkSnapshot['nativeExecution']
  if (body.native_execution != null) {
    const execution = object(body.native_execution)
    if (typeof execution.available !== 'boolean' || !(execution.unavailable_reason === null || typeof execution.unavailable_reason === 'string')) throw new ThreadProtocolError('会话执行配置无效')
    nativeExecution = {available: execution.available, unavailableReason: execution.unavailable_reason as string | null}
  }
  const works = body.works.map((raw): WorkRecord => {
    const work = object(raw)
    const workId = id(work.work_id)
    const context = object(work.task_context)
    const binding = object(context.binding)
    if (binding.thread_id !== threadId || binding.work_id !== workId
        || context.goal_revision !== work.goal_revision || !Array.isArray(context.model_contexts)
        || !Array.isArray(context.resource_refs)) throw new ThreadProtocolError('工作上下文关联无效')
    if (typeof work.goal !== 'string' || !work.goal.trim() || exceedsCapacity(work.goal.length,'input_text_chars')
        || !['ready', 'queued', 'running', 'completed', 'failed', 'cancelled', 'interrupted', 'blocked'].includes(String(work.status))
        || !(work.blocked_reason === null || typeof work.blocked_reason === 'string')
        || (work.conversation_mode !== undefined && typeof work.conversation_mode !== 'boolean')
        || !Array.isArray(work.messages) || (!work.messages.length && work.conversation_mode !== true) || exceedsCapacity(work.messages.length,'work_message_count')
        || work.messages.some(message => typeof message !== 'string' || !message.trim())) throw new ThreadProtocolError('工作内容无效')
    if (revision(work.goal_revision, 1) > revision(work.revision, 1)) throw new ThreadProtocolError('目标修订无效')
    if ((work.start_available !== undefined && typeof work.start_available !== 'boolean')
        || (work.cancel_requested !== undefined && typeof work.cancel_requested !== 'boolean')
        || (work.start_unavailable_reason != null && (typeof work.start_unavailable_reason !== 'string' || work.start_unavailable_reason.length > 200))) throw new ThreadProtocolError('工作操作状态无效')
    return { workId, goal: work.goal, goalRevision: revision(work.goal_revision, 1),
      revision: revision(work.revision, 1), status: work.status as string,
      latestAttemptId: work.latest_attempt_id == null ? null : id(work.latest_attempt_id),
      startAvailable: typeof work.start_available === 'boolean' ? work.start_available : false,
      cancelRequested: work.cancel_requested === true, conversationMode: work.conversation_mode === true,
      startUnavailableReason: work.start_unavailable_reason == null ? null : String(work.start_unavailable_reason),
      blockedReason: work.blocked_reason as string | null, messages: work.messages as string[] }
  })
  if (new Set(works.map(work => work.workId)).size !== works.length) throw new ThreadProtocolError('工作身份重复')
  let professionalSnapshot: ThreadSnapshot | undefined
  if (modelContext) {
    const inherited = Object.fromEntries(Object.entries(body).filter(([key]) =>
      !['minimum_protocol_version', 'selected_model_context_id', 'task_context', 'works', 'native_execution'].includes(key)))
    if (body.current_attempt !== null) inherited.current_attempt = Object.fromEntries(Object.entries(object(body.current_attempt)).filter(([key]) => key !== 'work_id'))
    professionalSnapshot = parseThreadSnapshot({ ...inherited, schema: 'capstone-thread-snapshot/1' })
  }
  return { threadId, runId, modelContext, selectedModelContextId, lastEventSeq, baseEventSeq, works, professionalSnapshot,
    currentAttempt, runtimeMode, ...(nativeExecution ? {nativeExecution} : {}),
    ...(body.session_type == null ? {} : {sessionType: body.session_type as WorkSnapshot['sessionType']}),
    ...(body.session_title == null ? {} : {sessionTitle: parseSessionTitle(body.session_title)}),
    toDocument: () => structuredClone(body) }
}

export function buildSendMessageCommand(threadId: string, runId: string, commandId: string, idempotencyKey: string,
                                       workId: string, expectedRevision: number, text: string, submission?: InputSubmission, sourceAttemptId?: string): WorkCommand {
  const command: WorkCommand = {...buildWorkCommand(threadId, runId, commandId, idempotencyKey, workId, expectedRevision, text), kind: 'send_message'}
  if (submission) {
    const input = object(submission.input)
    const choice = object(submission.context_selection)
    if (input.text !== text || !['text', 'skill_invocation'].includes(String(input.kind))
        || !Array.isArray(choice.include_refs) || !Array.isArray(choice.exclude_refs)
        || [...choice.include_refs, ...choice.exclude_refs].some(ref => typeof ref !== 'string')
        || (input.kind === 'skill_invocation' && (typeof input.skill_id !== 'string' || !input.skill_id || typeof input.skill_version !== 'string' || !input.skill_version || !submission.resource_profile))) throw new ThreadProtocolError('输入资料无效')
    if (submission.resource_profile && (!['delegated_pi', 'direct_pi', 'harness_engine'].includes(submission.resource_profile.profile_id) || typeof submission.resource_profile.revision !== 'string' || !submission.resource_profile.revision)) throw new ThreadProtocolError('输入资源无效')
    if (submission.material_refs !== undefined && (!Array.isArray(submission.material_refs) || exceedsCapacity(submission.material_refs.length,'inline_material_count')
        || submission.material_refs.some(ref => typeof ref !== 'string' || !/^material_[a-f0-9]{32}$/.test(ref)) || new Set(submission.material_refs).size !== submission.material_refs.length)) throw new ThreadProtocolError('输入资料无效')
    if(submission.context_product_refs!==undefined)parseContextProductRefs(submission.context_product_refs,threadId)
    if(submission.attachment_refs!==undefined&&(!Array.isArray(submission.attachment_refs)||exceedsCapacity(submission.attachment_refs.length,'ui_attachment_count')||submission.attachment_refs.some(ref=>!/^resource_[a-f0-9]{32}$/.test(ref))||new Set(submission.attachment_refs).size!==submission.attachment_refs.length))throw new ThreadProtocolError('待发送附件无效')
    command.payload = {text, ...structuredClone(submission)}
  }
  if (sourceAttemptId !== undefined) command.payload = {...command.payload, text, source_attempt_id: id(sourceAttemptId)}
  assertCapacity(new TextEncoder().encode(JSON.stringify(command)).byteLength,'command_bytes')
  return command
}

export function buildWorkCommand(threadId: string, runId: string, commandId: string, idempotencyKey: string,
                                 workId: string, expectedRevision: number, text: string,
                                 kind: 'work_message' | 'revise_goal' = 'work_message'): WorkCommand {
  if (!text.trim() || exceedsCapacity(text.length,'input_text_chars')) throw new ThreadProtocolError('请输入有效任务内容')
  if (kind !== 'work_message' && kind !== 'revise_goal') throw new ThreadProtocolError('工作操作无效')
  const command: WorkCommand = { schema: 'capstone-command/2', thread_id: id(threadId), run_id: id(runId),
    command_id: id(commandId), idempotency_key: id(idempotencyKey), kind,
    target: { kind: 'work', id: id(workId), expected_revision: revision(expectedRevision) }, payload: { text } }
  assertCapacity(new TextEncoder().encode(JSON.stringify(command)).byteLength,'command_bytes')
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
  if (command.schema !== 'capstone-command/2' || command.thread_id !== threadId) throw new ThreadProtocolError('工作命令身份无效')
  if (target.kind === 'model_workspace' && target.id === threadId && ['open_model','activate_model','close_model'].includes(String(command.kind))) {
    return buildModelWorkspaceCommand(threadId,id(command.run_id),id(command.command_id),id(command.idempotency_key),revision(target.expected_revision),command.kind as 'open_model'|'activate_model'|'close_model',payload)
  }
  if (target.kind !== 'work') throw new ThreadProtocolError('工作命令身份无效')
  if (command.kind === 'send_message' && typeof payload.text === 'string'
      && Object.keys(payload).every(key => ['text', 'input', 'context_selection', 'resource_profile', 'source_attempt_id', 'material_refs','context_product_refs','attachment_refs'].includes(key))) {
    const {text, source_attempt_id, ...submission} = payload
    return buildSendMessageCommand(threadId, id(command.run_id), id(command.command_id), id(command.idempotency_key), id(target.id), revision(target.expected_revision), text,
      Object.keys(submission).length ? submission as InputSubmission : undefined,
      source_attempt_id === undefined ? undefined : id(source_attempt_id))
  }
  if (command.kind === 'start_work' && Object.keys(payload).length === 0) return buildStartWorkCommand(threadId, id(command.run_id), id(command.command_id), id(command.idempotency_key), id(target.id), revision(target.expected_revision))
  if (command.kind === 'cancel_work' && Object.keys(payload).length === 0) return buildCancelWorkCommand(threadId, id(command.run_id), id(command.command_id), id(command.idempotency_key), id(target.id), revision(target.expected_revision))
  if ((command.kind === 'work_message' || command.kind === 'revise_goal') && typeof payload.text === 'string' && Object.keys(payload).length === 1) return buildWorkCommand(threadId, id(command.run_id), id(command.command_id), id(command.idempotency_key), id(target.id), revision(target.expected_revision), payload.text, command.kind)
  throw new ThreadProtocolError('工作命令无效')
}

export function buildModelWorkspaceCommand(threadId: string, runId: string, commandId: string, idempotencyKey: string,
  expectedRevision: number, kind: 'open_model' | 'activate_model' | 'close_model', payload: Record<string, unknown>): WorkCommand {
  const fields = Object.keys(payload)
  const validText = (value:unknown):value is string => typeof value === 'string' && value.trim().length > 0 && !exceedsCapacity(value.length,'ui_result_text_chars')
  if (kind === 'open_model' ? !validText(payload.model_id) || fields.some(key=>!['model_id','model_revision'].includes(key)) ||
      (payload.model_revision !== undefined && !validText(payload.model_revision))
    : !['activate_model','close_model'].includes(kind) || fields.length !== 1 || !validText(payload.entry_id)) throw new ThreadProtocolError('模型操作无效')
  const command: WorkCommand = {schema:'capstone-command/2',thread_id:id(threadId),run_id:id(runId),command_id:id(commandId),idempotency_key:id(idempotencyKey),kind,
    target:{kind:'model_workspace',id:id(threadId),expected_revision:revision(expectedRevision)},payload:structuredClone(payload) as Record<string,string>}
  assertCapacity(new TextEncoder().encode(JSON.stringify(command)).byteLength,'command_bytes')
  return command
}
