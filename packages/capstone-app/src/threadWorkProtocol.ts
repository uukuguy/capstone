import {parseMissionRefs,type MissionRef} from './missions'
import {assertCapacity,exceedsCapacity} from './applicationCapacity'
import { parseContext, parseThreadSnapshot, ThreadProtocolError, type ModelContextSnapshot, type ThreadSnapshot } from './threadProtocol'
import { parseSessionTitle, type SessionTitle } from './sessionTitle'
import {parseSessionSkills,type SessionSkills} from './sessionSkills'
import type { InputSubmission } from './threadInput'
import {validLlmProfileId} from './threadInput'
import {parseContextProductRefs} from './threadProducts'
import {parseGoalMode,goalCommand,type GoalMode,type GoalControl} from './goalMode'
import type { AttemptPhase, RuntimeMode } from './threadProtocol'

export type QueuedInstruction = {id:string;text:string;attemptId:string;sequence:number;mode?:'interrupt';state:'pending'|'delivering'|'delivery_unknown'|'admitted'|'withdrawn'}
export type SessionGoalPlan = {
  criteria: string[]
  steps: { instruction: string; expectedResult: string }[]
  stepIndex: number
}
export type TaskHandoff = {thread_id:string;work_id:string;work_revision:number;revision_ref:string;mission_id?:string;mission_revision?:number}

function parseTaskHandoff(value:unknown):TaskHandoff {
  const row = object(value)
  const hasMission = row.mission_id !== undefined || row.mission_revision !== undefined
  if (Object.keys(row).length !== (hasMission ? 6 : 4)) throw new ThreadProtocolError('续作引用无效')
  return {thread_id:id(row.thread_id),work_id:id(row.work_id),
    work_revision:revision(row.work_revision,1),revision_ref:id(row.revision_ref),
    ...(hasMission ? {mission_id:id(row.mission_id),mission_revision:revision(row.mission_revision,1)} : {})}
}

const handoffCommand = '/continue-from'
export function isHandoffInstruction(text:string):boolean {
  return text === handoffCommand || text.startsWith(handoffCommand + ' ')
}

export function handoffInstruction(text:string):{text:string;source:TaskHandoff}|null {
  if (!isHandoffInstruction(text)) return null
  const [header,...instruction] = text.split('\n')
  const fields = header.slice(handoffCommand.length).trim().split('/')
  const [thread_id,work_id,work_revision,revision_ref,mission_id,missionRevision] = fields
  const nextText = instruction.join('\n').trim()
  if (![4,6].includes(fields.length) || !/^[1-9][0-9]*$/.test(work_revision) || !nextText
      || (fields.length === 6 && !/^[1-9][0-9]*$/.test(missionRevision)))
    throw new ThreadProtocolError('请在续作引用下另起一行填写新指令。')
  return {text:nextText,source:parseTaskHandoff({thread_id,work_id,work_revision:Number(work_revision),revision_ref,
    ...(mission_id === undefined ? {} : {mission_id,mission_revision:Number(missionRevision)})})}
}

export type TaskDecision = 'accept' | 'request_changes'
export type WorkRecord = {
  instructionQueue?:QueuedInstruction[]
  instructionQueueAvailable?:boolean
  workId: string; goal: string; goalRevision: number; revision: number; status: string
  blockedReason: string | null; messages: string[]
  latestAttemptId: string | null; startAvailable: boolean; startUnavailableReason: string | null
  cancelRequested?: boolean
  contextProductRefs?:InputSubmission['context_product_refs']
  conversationMode?: boolean
  goalMode?: GoalMode
  goalPlan?: SessionGoalPlan
  goalPlanPending?: boolean
  taskStateRevision?: string
}
export type WorkAttempt = { turnId: string; attemptId: string; phase: AttemptPhase;
  targetModelContextId: string | null; runtimeMode: RuntimeMode; workId: string | null }
export type WorkSnapshot = {
  missionRefs?:MissionRef[]
  sessionTitle?: SessionTitle
  sessionSkills?: SessionSkills
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
  command_id: string; idempotency_key: string; kind: 'queue_instruction' | 'withdraw_instruction' | 'work_message' | 'revise_goal' | 'start_work' | 'cancel_work' | 'send_message' | 'record_task_decision' | 'open_model' | 'activate_model' | 'close_model' | GoalControl
  target: { kind: 'work' | 'model_workspace'; id: string; expected_revision: number }
  payload: ({ text: string; source_attempt_id?: string; task_handoff?: TaskHandoff } & Partial<InputSubmission>) | Record<string, string|number>
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

function parseTaskDecision(value: unknown): TaskDecision {
  if (value === 'accept' || value === 'request_changes') return value
  throw new ThreadProtocolError('任务验收决定无效')
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
    if(work.instruction_queue_available!==undefined&&typeof work.instruction_queue_available!=='boolean')throw new ThreadProtocolError('指令队列能力无效')
    let instructionQueue:QueuedInstruction[]|undefined
    if(work.instruction_queue!==undefined){
      if(!Array.isArray(work.instruction_queue))throw new ThreadProtocolError('指令队列无效')
      instructionQueue=work.instruction_queue.map(raw=>{
        const entry=object(raw)
        if((entry.mode!==undefined&&entry.mode!=='interrupt')||typeof entry.text!=='string'||!entry.text.trim()||!['pending','delivering','delivery_unknown','admitted','withdrawn'].includes(String(entry.state)))throw new ThreadProtocolError('队列指令无效')
        return {id:id(entry.id),text:entry.text,attemptId:id(entry.attempt_id),sequence:revision(entry.sequence,1),state:entry.state as QueuedInstruction['state'],...(entry.mode==='interrupt'?{mode:'interrupt' as const}:{})}
      })
      if(new Set(instructionQueue.map(entry=>entry.id)).size!==instructionQueue.length)throw new ThreadProtocolError('队列指令身份重复')
      instructionQueue.sort((a,b)=>a.sequence-b.sequence)
    }
    const goalPlan = work.goal_plan === undefined ? undefined : parseSessionGoalPlan(work.goal_plan)
    return {instructionQueue,instructionQueueAvailable:work.instruction_queue_available===true, ...(work.context_product_refs===undefined?{}:{contextProductRefs:parseContextProductRefs(work.context_product_refs,threadId)}),workId, goal: work.goal, goalRevision: revision(work.goal_revision, 1),
      revision: revision(work.revision, 1), status: work.status as string,
      latestAttemptId: work.latest_attempt_id == null ? null : id(work.latest_attempt_id),
      startAvailable: typeof work.start_available === 'boolean' ? work.start_available : false,
      cancelRequested: work.cancel_requested === true, conversationMode: work.conversation_mode === true,
      ...(work.goal_mode===undefined?{}:{goalMode:parseGoalMode(work.goal_mode)}),
      taskStateRevision: work.task_state == null ? undefined : id(object(work.task_state).revision_ref),
      goalPlan, goalPlanPending: work.goal_plan_pending === true,
      startUnavailableReason: work.start_unavailable_reason == null ? null : String(work.start_unavailable_reason),
      blockedReason: work.blocked_reason as string | null, messages: work.messages as string[] }
  })
  if (new Set(works.map(work => work.workId)).size !== works.length) throw new ThreadProtocolError('工作身份重复')
  let professionalSnapshot: ThreadSnapshot | undefined
  if (modelContext) {
    const inherited = Object.fromEntries(Object.entries(body).filter(([key]) =>
      !['minimum_protocol_version', 'selected_model_context_id', 'task_context', 'works', 'native_execution', 'mission_refs'].includes(key)))
    if (body.current_attempt !== null) inherited.current_attempt = Object.fromEntries(Object.entries(object(body.current_attempt)).filter(([key]) => key !== 'work_id'))
    professionalSnapshot = parseThreadSnapshot({ ...inherited, schema: 'capstone-thread-snapshot/1' })
  }
  return { missionRefs:parseMissionRefs(body.mission_refs), threadId, runId, modelContext, selectedModelContextId, lastEventSeq, baseEventSeq, works, professionalSnapshot,
    currentAttempt, runtimeMode, ...(nativeExecution ? {nativeExecution} : {}),
    ...(body.session_type == null ? {} : {sessionType: body.session_type as WorkSnapshot['sessionType']}),
    ...(body.session_title == null ? {} : {sessionTitle: parseSessionTitle(body.session_title)}),
    ...(body.session_skills == null ? {} : {sessionSkills:parseSessionSkills(body.session_skills)}),
    toDocument: () => structuredClone(body) }
}

export function buildSendMessageCommand(threadId: string, runId: string, commandId: string, idempotencyKey: string,
                                       workId: string, expectedRevision: number, text: string, submission?: InputSubmission, sourceAttemptId?: string, handoff?: TaskHandoff): WorkCommand {
  const command: WorkCommand = {...buildWorkCommand(threadId, runId, commandId, idempotencyKey, workId, expectedRevision, text), kind: 'send_message'}
  if (submission) {
    if(submission.llm_profile_id!==undefined&&!validLlmProfileId(submission.llm_profile_id))throw new ThreadProtocolError('LLM 选择无效')
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
  if (handoff !== undefined) {
    if (sourceAttemptId !== undefined || handoff.thread_id === threadId) throw new ThreadProtocolError('请选择另一会话的一个续作来源。')
    command.payload = {...command.payload, text, task_handoff:parseTaskHandoff(handoff)}
  }
  assertCapacity(new TextEncoder().encode(JSON.stringify(command)).byteLength,'command_bytes')
  return command
}

export function buildWorkCommand(threadId: string, runId: string, commandId: string, idempotencyKey: string,
                                 workId: string, expectedRevision: number, text: string,
                                 kind: 'work_message' | 'revise_goal' = 'work_message', contextProductRefs?:InputSubmission['context_product_refs']): WorkCommand {
  if (!text.trim() || exceedsCapacity(text.length,'input_text_chars')) throw new ThreadProtocolError('请输入有效任务内容')
  if (kind !== 'work_message' && kind !== 'revise_goal') throw new ThreadProtocolError('工作操作无效')
  const command: WorkCommand = { schema: 'capstone-command/2', thread_id: id(threadId), run_id: id(runId),
    command_id: id(commandId), idempotency_key: id(idempotencyKey), kind,
    target: { kind: 'work', id: id(workId), expected_revision: revision(expectedRevision) }, payload: { text } }
  if(contextProductRefs!==undefined)command.payload={...command.payload,text,context_product_refs:parseContextProductRefs(contextProductRefs,threadId)}
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

export function buildTaskDecisionCommand(threadId: string, runId: string, commandId: string, idempotencyKey: string,
  workId: string, expectedRevision: number, revisionRef: string, decision: TaskDecision): WorkCommand {
  return {...buildStartWorkCommand(threadId, runId, commandId, idempotencyKey, workId, expectedRevision),
    kind: 'record_task_decision', payload: {revision_ref: id(revisionRef), decision: parseTaskDecision(decision)}}
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
  if (command.kind === 'record_task_decision' && Object.keys(payload).length === 2) {
    return buildTaskDecisionCommand(threadId, id(command.run_id), id(command.command_id), id(command.idempotency_key),
      id(target.id), revision(target.expected_revision, 1), id(payload.revision_ref), parseTaskDecision(payload.decision))
  }
  if(command.kind==='queue_instruction'||command.kind==='withdraw_instruction'){
    const field=command.kind==='queue_instruction'?'text':'instruction_id'
    const interrupt=command.kind==='queue_instruction'&&payload.mode==='interrupt'
    if(Object.keys(payload).length!==(interrupt?2:1)||typeof payload[field]!=='string'||!(payload[field] as string).trim()||(field==='text'&&exceedsCapacity((payload[field] as string).length,'input_text_chars')))throw new ThreadProtocolError('队列命令无效')
    return {schema:'capstone-command/2',thread_id:threadId,run_id:id(command.run_id),command_id:id(command.command_id),idempotency_key:id(command.idempotency_key),kind:command.kind,target:{kind:'work',id:id(target.id),expected_revision:revision(target.expected_revision,1)},payload:{[field]:field==='instruction_id'?id(payload[field]):payload[field] as string,...(interrupt?{mode:'interrupt'}:{})}}
  }
  if (['start_goal','pause_goal','resume_goal','cancel_goal','revise_goal_objective'].includes(String(command.kind))) {
    if(!Object.values(payload).every(value=>typeof value==='string'||typeof value==='number'))throw new ThreadProtocolError('目标命令无效')
    return goalCommand(threadId,id(command.run_id),id(command.command_id),id(command.idempotency_key),
      id(target.id),revision(target.expected_revision,1),command.kind as GoalControl,payload as Record<string,string|number>)
  }
  if (command.kind === 'send_message' && typeof payload.text === 'string'
      && Object.keys(payload).every(key => ['text', 'input', 'context_selection', 'resource_profile', 'source_attempt_id', 'task_handoff', 'material_refs','context_product_refs','attachment_refs','deep_research','llm_profile_id'].includes(key))) {
    const {text, source_attempt_id, task_handoff, ...submission} = payload
    return buildSendMessageCommand(threadId, id(command.run_id), id(command.command_id), id(command.idempotency_key), id(target.id), revision(target.expected_revision), text,
      Object.keys(submission).length ? submission as InputSubmission : undefined,
      source_attempt_id === undefined ? undefined : id(source_attempt_id),
      task_handoff === undefined ? undefined : parseTaskHandoff(task_handoff))
  }
  if (command.kind === 'start_work' && Object.keys(payload).length === 0) return buildStartWorkCommand(threadId, id(command.run_id), id(command.command_id), id(command.idempotency_key), id(target.id), revision(target.expected_revision))
  if (command.kind === 'cancel_work' && Object.keys(payload).length === 0) return buildCancelWorkCommand(threadId, id(command.run_id), id(command.command_id), id(command.idempotency_key), id(target.id), revision(target.expected_revision))
  if ((command.kind === 'work_message' || command.kind === 'revise_goal') && typeof payload.text === 'string' && Object.keys(payload).every(key=>['text','context_product_refs'].includes(key))) return buildWorkCommand(threadId, id(command.run_id), id(command.command_id), id(command.idempotency_key), id(target.id), revision(target.expected_revision), payload.text, command.kind, payload.context_product_refs===undefined?undefined:parseContextProductRefs(payload.context_product_refs,threadId))
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


function parseSessionGoalPlan(value: unknown): SessionGoalPlan {
  const receipt = object(value)
  const plan = object(receipt.plan)
  if (receipt.schema !== 'capstone-session-goal-plan-receipt/1' ||
      plan.schema !== 'capstone-session-goal-plan/1' ||
      !Array.isArray(plan.criteria) || !plan.criteria.every(item => typeof item === 'string') ||
      !Array.isArray(plan.steps)) throw new ThreadProtocolError('目标计划无效')
  const steps = plan.steps.map(value => {
    const step = object(value)
    if (typeof step.instruction !== 'string' || typeof step.expected_result !== 'string')
      throw new ThreadProtocolError('目标步骤无效')
    return {instruction: step.instruction, expectedResult: step.expected_result}
  })
  const stepIndex = receipt.step_index === undefined ? 0 : revision(receipt.step_index, 0)
  if (stepIndex >= steps.length) throw new ThreadProtocolError('目标步骤位置无效')
  return {criteria: plan.criteria, steps, stepIndex}
}
