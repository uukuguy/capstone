import type { EventEnvelope } from './threadProtocol'

type RecordValue = Record<string, unknown>
export type GraphOwner = { thread_id: string; work_id: string; research_id: string; goal_revision: number }
export type GraphCheckpoint = { ref: string; revision: number }
export type GraphBinding = { result_ref: string; slot: string; input_name?: string; producer_step_id?: string }
export type GraphSourceVersion = { ref: string; revision: string }
export type GraphNode = {
  id: string; purpose: string; questions: string[]; checks: string[]; depends_on: string[]; expected_outputs: string[];
  mode: string; execution: string; instruction: string; outputs: { slot: string; kind: string; description: string }[];
  inputs: { name: string; result_ref?: string; from?: { step_id: string; slot: string } }[];
  phase: string; applicability: string; execution_revision: number; execute_action_id: string | null; assess_action_id: string | null;
  blocked_by: string[]; wait_reason: string | null; input_bindings: GraphBinding[]; output_bindings: GraphBinding[];
  settled_status: string | null;
  source_refs?: string[]; selected_source_versions?: GraphSourceVersion[];
}
export type GraphAction = { id: string; owner: GraphOwner; attempt_id: string; step_id: string; kind: string; execution_revision: number; graph_ref: string; graph_revision: number; input_bindings: GraphBinding[]; source_refs?: string[]; source_versions?: GraphSourceVersion[] }
export type GraphResult = {
  schema: string; result_ref: string; producer: { step_id: string; action_id: string; execution_revision: number; attempt_id: string };
  slot: string; kind: string; summary: string; scope: string; consumed_results: string[]; source_versions: { ref: string; revision: string | null }[];
  method: Record<string, string>; supersedes: string[]; recompute_reason: { kind: string; refs: string[]; diagnostic?: string } | null;
}
export type ExecutionGraphSnapshot = { schema: string; graph_ref: string; graph_revision: number; goal: string; output_mode: string; model_revision_reason: string | null; nodes: GraphNode[]; actions: GraphAction[]; results: GraphResult[] }
export type GraphTool = { id: string; name: string; status: 'running' | 'completed' | 'failed'; startedAt?: string; finishedAt?: string; durationMs?: number; executionMs?: number; operation?: string; output?: string; warning?: string; failure?: string; actionId?: string; actionKind?: string; origin?: 'parent'; returnLimitations?: {count:number;notes:string[]} }
export type GraphResponse = { number: number; ms: number; usage?: RecordValue; startedAt?: string; finishedAt?: string; toolCallIds?: string[]; stopReason?: string; responseText?: string; toolRequests?: { id: string; name: string; operation?: string }[] }
export type GraphExecution = { action: GraphAction; node: GraphNode; tools: GraphTool[]; responses: GraphResponse[]; nativeStatus?: string; resultSummary?: string; startedAt?: string; finishedAt?: string; durationMs?: number; executionStartedAt?: string; executionFinishedAt?: string; executionIntervalMs?: number; modelResponseCount?: number; turnCount?: number }
export type GraphParentResponse = { id: string; startedAt: string; finishedAt: string; ms: number; kind: string; errorCode?:string; errorStatus?:number }
export type ExecutionGraph = {
  owner: GraphOwner; taskId: string; current: ExecutionGraphSnapshot;
  checkpoints: { checkpoint: GraphCheckpoint; graph: ExecutionGraphSnapshot }[];
  revisions: { graph: ExecutionGraphSnapshot; occurredAt: string }[];
  executions: GraphExecution[];
  parentResponses?: GraphParentResponse[];
  parentPendingResponse?: {id: string; startedAt: string};
  controlCalls: { callId: string; name: string; checkpoint: GraphCheckpoint; graphRef: string; actionId?: string; stepId?: string }[];
  controlEvents: { id: string; checkpoint: GraphCheckpoint; graphRef: string; kind: string; summary?: string }[];
}

const object = (v: unknown): v is RecordValue => !!v && typeof v === 'object' && !Array.isArray(v)
const text = (v: unknown): v is string => typeof v === 'string' && v.trim().length > 0
const enumValue = (v: unknown, values: readonly string[]): v is string => typeof v === 'string' && values.includes(v)
const ref = (v: unknown): v is string => text(v) && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$/.test(v)
const id = (v: unknown): v is string => text(v) && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(v)
const positive = (v: unknown): v is number => Number.isSafeInteger(v) && Number(v) > 0
const nonnegative = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v) && v >= 0
const texts = (v: unknown): v is string[] => Array.isArray(v) && v.every(text)
const unique = (values: readonly unknown[]) => new Set(values).size === values.length
const canonical = (v: unknown): string => JSON.stringify(v, (_key, child) => object(child) ? Object.fromEntries(Object.entries(child).sort(([a], [b]) => a.localeCompare(b))) : child)
const equal = (a: unknown, b: unknown) => canonical(a) === canonical(b)
const ownerValid = (v: unknown): v is GraphOwner => object(v) && ref(v.thread_id) && ref(v.work_id) && ref(v.research_id) && positive(v.goal_revision)
const checkpointValid = (v: unknown): v is GraphCheckpoint => object(v) && ref(v.ref) && positive(v.revision)
const nullableRef = (v: unknown) => v === null || ref(v)
const inputBindingsValid = (v: unknown) => Array.isArray(v) && v.every(b => object(b) && ref(b.result_ref) && id(b.slot) &&
  (b.input_name === undefined || id(b.input_name)) && (b.producer_step_id === undefined || id(b.producer_step_id)))
const outputBindingsValid = (v: unknown) => Array.isArray(v) && v.every(b => object(b) && ref(b.result_ref) && id(b.slot))
const sourceScopeValid = (scope: RecordValue, versionsKey: string) => {
  const refs = scope.source_refs, versions = scope[versionsKey]
  // Historical projections did not record a node-level source selection.
  if (refs === undefined && versions === undefined) return true
  return Array.isArray(refs) && refs.every(ref) && unique(refs) && Array.isArray(versions) &&
    versions.every(v => object(v) && ref(v.ref) && ref(v.revision) && refs.includes(v.ref)) && unique(versions.map(v => v.ref))
}
const phases = ['pending', 'ready', 'executing', 'executed', 'recorded', 'assessing', 'success', 'limited', 'failure']
const nativeStatuses = ['completed', 'failed', 'cancelled', 'unknown']
const recomputeKinds = ['source_changed', 'method_changed', 'missing_result', 'discrepancy']
const toolActivities = ['start', 'end', 'tool_execution_start', 'tool_execution_end']

function snapshotValid(value: unknown, owner: GraphOwner, attemptId: string): value is ExecutionGraphSnapshot {
  if (!object(value) || value.schema !== 'capstone-enterprise-graph/2' || !ref(value.graph_ref) || !positive(value.graph_revision) ||
    !text(value.goal) || !enumValue(value.output_mode, ['text', 'files']) || !(value.model_revision_reason === null || text(value.model_revision_reason)) ||
    !Array.isArray(value.nodes) || !value.nodes.length || !Array.isArray(value.actions) || !Array.isArray(value.results)) return false
  const nodes = value.nodes, currentActions = value.actions
  if (!nodes.every(n => object(n) && id(n.id) && text(n.purpose) && texts(n.questions) && texts(n.checks) && texts(n.expected_outputs) &&
    texts(n.depends_on) && unique(n.depends_on) && enumValue(n.mode, ['execute', 'synthesis']) && enumValue(n.execution, ['parent', 'delegated']) && text(n.instruction) &&
    Array.isArray(n.outputs) && n.outputs.every(o => object(o) && id(o.slot) && enumValue(o.kind, ['observation', 'artifact']) && text(o.description)) && unique(n.outputs.map(o => o.slot)) &&
    Array.isArray(n.inputs) && n.inputs.every(i => object(i) && id(i.name) && (ref(i.result_ref) && i.from === undefined || i.result_ref === undefined && object(i.from) && id(i.from.step_id) && id(i.from.slot))) && unique(n.inputs.map(i => i.name)) &&
    enumValue(n.phase, phases) && enumValue(n.applicability, ['current', 'stale']) && positive(n.execution_revision) && nullableRef(n.execute_action_id) && nullableRef(n.assess_action_id) &&
    texts(n.blocked_by) && (n.wait_reason === null || text(n.wait_reason)) && inputBindingsValid(n.input_bindings) && outputBindingsValid(n.output_bindings) && sourceScopeValid(n, 'selected_source_versions') && (n.settled_status === null || enumValue(n.settled_status, nativeStatuses)))) return false
  if (!unique(nodes.map(n => n.id))) return false
  const byId = new Map(nodes.map(n => [n.id, n]))
  if (nodes.some(n => n.depends_on.some((dep: string) => !byId.has(dep)) || n.blocked_by.some((dep: string) => !byId.has(dep)) ||
    n.inputs.some((i: GraphNode['inputs'][number]) => i.from && (!n.depends_on.includes(i.from.step_id) || !byId.get(i.from.step_id)?.outputs.some((o: GraphNode['outputs'][number]) => o.slot === i.from!.slot))))) return false
  const visiting = new Set<string>(), visited = new Set<string>()
  const acyclic = (key: string): boolean => {
    if (visiting.has(key)) return false
    if (visited.has(key)) return true
    visiting.add(key)
    if (!byId.get(key)!.depends_on.every(acyclic)) return false
    visiting.delete(key); visited.add(key); return true
  }
  if (!nodes.every(n => acyclic(n.id))) return false
  if (!value.actions.every(a => object(a) && ref(a.id) && equal(a.owner, owner) && a.attempt_id === attemptId && byId.has(a.step_id) &&
    enumValue(a.kind, ['execute', 'assess']) && positive(a.execution_revision) && ref(a.graph_ref) && positive(a.graph_revision) && inputBindingsValid(a.input_bindings) &&
    byId.get(a.step_id)[a.kind === 'execute' ? 'execute_action_id' : 'assess_action_id'] === a.id && byId.get(a.step_id).execution_revision === a.execution_revision &&
    equal(a.input_bindings, byId.get(a.step_id).input_bindings) && sourceScopeValid(a, 'source_versions') &&
    equal(a.source_refs, byId.get(a.step_id).source_refs) && equal(a.source_versions, byId.get(a.step_id).selected_source_versions)) || !unique(value.actions.map(a => a.id))) return false
  if (nodes.some(n => {
    const kind = ['executing', 'executed'].includes(n.phase) ? 'execute' : ['recorded', 'assessing'].includes(n.phase) ? 'assess' : undefined
    return kind && !currentActions.some(a => a.id === n[`${kind}_action_id`] && a.kind === kind && a.step_id === n.id)
  })) return false
  if (!unique(nodes.flatMap(n => [n.execute_action_id, n.assess_action_id].filter(Boolean)))) return false
  return unique(value.results.map(r => r?.result_ref)) && value.results.every(r => object(r) && r.schema === 'capstone-task-result/1' && ref(r.result_ref) &&
    object(r.producer) && id(r.producer.step_id) && ref(r.producer.action_id) && positive(r.producer.execution_revision) && r.producer.attempt_id === attemptId &&
    id(r.slot) && enumValue(r.kind, ['observation', 'artifact']) && text(r.summary) && text(r.scope) && texts(r.consumed_results) && texts(r.supersedes) &&
    Array.isArray(r.source_versions) && r.source_versions.every(v => object(v) && ref(v.ref) && (v.revision === null || ref(v.revision))) &&
    object(r.method) && Object.values(r.method).every(v => typeof v === 'string') &&
    (r.recompute_reason === null || object(r.recompute_reason) && enumValue(r.recompute_reason.kind, recomputeKinds) && texts(r.recompute_reason.refs) &&
      (r.recompute_reason.diagnostic === undefined || text(r.recompute_reason.diagnostic))))
}

function elapsed(start?: string, finish?: string) {
  if (!start || !finish) return undefined
  const a = Date.parse(start), b = Date.parse(finish)
  return Number.isFinite(a) && Number.isFinite(b) && b >= a ? b - a : undefined
}

/** Read only admitted public wire. Never infer a business node from a tool name or the active sibling. */
export function projectExecutionGraph(events: readonly EventEnvelope[], attemptId: string): ExecutionGraph | undefined {
  let output: ExecutionGraph | undefined
  const actions = new Map<string, GraphExecution>(), results = new Map<string, GraphResult>()
  const checkpoints = new Map<string, { checkpoint: GraphCheckpoint; graph: ExecutionGraphSnapshot }>()
  const checkpointRevisions = new Map<number, string>(), bindings = new Map<string, { actionId: string; name: string }>()
  const eligible = events.filter(e => e.visibility === 'public' && e.eventType === 'runtime_event' && e.attemptId === attemptId)
  // Snapshots admit action leases first. Native events can precede their immutable binding frame.
  for (const event of eligible) {
    const p = event.payload.research_graph
    if (!object(p) || p.type !== 'enterprise_graph_progress' || p.attempt_id !== attemptId || !ownerValid(p.owner) || p.owner.thread_id !== event.threadId ||
      !ref(p.task_id) || !checkpointValid(p.checkpoint) || !Array.isArray(p.events) || !p.events.every(object) ||
      output && (!equal(output.owner, p.owner) || output.taskId !== p.task_id) || !snapshotValid(p.graph, p.owner, attemptId)) continue
    const g = p.graph, checkpoint = p.checkpoint
    const existing = checkpoints.get(checkpoint.ref)
    if (existing && (!equal(existing.checkpoint, checkpoint) || !equal(existing.graph, g)) || checkpointRevisions.has(checkpoint.revision) && checkpointRevisions.get(checkpoint.revision) !== checkpoint.ref) continue
    if (existing) continue
    if (output && (checkpoint.revision < output.checkpoints.at(-1)!.checkpoint.revision || g.graph_revision < output.current.graph_revision ||
      g.graph_revision === output.current.graph_revision && g.graph_ref !== output.current.graph_ref)) continue
    if (g.actions.some(a => actions.has(a.id) && !equal(actions.get(a.id)!.action, a)) || g.results.some(r => results.has(r.result_ref) && !equal(results.get(r.result_ref), r))) continue
    const definition = (node: GraphNode) => Object.fromEntries(['id', 'purpose', 'questions', 'checks', 'depends_on', 'expected_outputs', 'mode', 'execution', 'instruction', 'outputs', 'inputs', 'source_refs', 'selected_source_versions'].map(key => [key, node[key as keyof GraphNode]]))
    if (g.nodes.some(n => [n.execute_action_id, n.assess_action_id].some(actionId => {
      const previous = actionId ? actions.get(actionId) : undefined
      return previous && (previous.action.step_id !== n.id || previous.action.execution_revision !== n.execution_revision || !equal(previous.action.input_bindings, n.input_bindings) || !equal(definition(previous.node), definition(n)))
    }))) continue
    const knownActionIds = new Set([...actions.keys(), ...g.actions.map(a => a.id)])
    if (p.action_id !== undefined && (!ref(p.action_id) || !knownActionIds.has(p.action_id))) continue
    if (p.events.some(e => e.step_id !== undefined && !g.nodes.some(n => n.id === e.step_id) || e.action_id !== undefined && (!ref(e.action_id) || !knownActionIds.has(e.action_id)))) continue
    if (p.control !== undefined && (!object(p.control) || !ref(p.control.tool_call_id) || !['plan', 'start', 'record', 'assess', 'revise', 'inspect', 'finish', 'resolve'].some(operation => p.control && (p.control as RecordValue).tool_name === `agent_research_${operation}`))) continue
    const control = object(p.control) ? p.control : undefined
    const priorControl = output?.controlCalls.find(c => c.callId === control?.tool_call_id)
    if (priorControl && (priorControl.name !== control!.tool_name || priorControl.graphRef !== g.graph_ref || !equal(priorControl.checkpoint, checkpoint))) continue
    output ??= { owner: p.owner, taskId: p.task_id, current: g, checkpoints: [], revisions: [], executions: [], controlEvents: [], controlCalls: [] }
    const saved = { checkpoint, graph: g }
    if (!existing) { checkpoints.set(checkpoint.ref, saved); checkpointRevisions.set(checkpoint.revision, checkpoint.ref); output.checkpoints.push(saved) }
    if (!output.revisions.some(r => r.graph.graph_ref === g.graph_ref)) output.revisions.push({ graph: g, occurredAt: event.occurredAt })
    output.current = g
    if (control && !priorControl) {
      const exact = typeof p.action_id === 'string' && ['start', 'record', 'assess', 'inspect', 'resolve'].some(operation => control.tool_name === `agent_research_${operation}`)
        ? actions.get(p.action_id)?.action ?? g.actions.find(action => action.id === p.action_id) : undefined
      output.controlCalls.push({ callId: String(control.tool_call_id), name: String(control.tool_name), checkpoint, graphRef: g.graph_ref,
        ...(exact ? { actionId: exact.id, stepId: exact.step_id } : {}) })
    }
    for (const a of g.actions) if (!actions.has(a.id)) actions.set(a.id, { action: a, node: g.nodes.find(n => n.id === a.step_id)!, tools: [], responses: [] })
    for (const execution of actions.values()) {
      const n = g.nodes.find(n => n.id === execution.action.step_id && n.execution_revision === execution.action.execution_revision)
      if (n) { execution.node = n; if (n.settled_status) execution.nativeStatus = n.settled_status }
    }
    for (const r of g.results) results.set(r.result_ref, r)
    for (const [index, e] of p.events.entries()) {
      const execution = typeof e.action_id === 'string' ? actions.get(e.action_id) : undefined
      if (execution?.action.kind === 'execute' && e.step_id === execution.action.step_id && e.execution_revision === execution.action.execution_revision) {
        if (e.kind === 'node_started') execution.executionStartedAt ??= event.occurredAt
        if (e.kind === 'node_execution_settled') execution.executionFinishedAt ??= event.occurredAt
        execution.executionIntervalMs = elapsed(execution.executionStartedAt, execution.executionFinishedAt)
      }
      if (enumValue(e.kind, ['graph_committed', 'graph_delivery_committed'])) output.controlEvents.push({ id: `${event.eventId}:${index}`, checkpoint, graphRef: g.graph_ref, kind: e.kind, summary: typeof e.summary === 'string' ? e.summary : typeof e.model_revision_reason === 'string' ? e.model_revision_reason : undefined })
      if (e.kind === 'node_settled' && typeof e.action_id === 'string' && actions.has(e.action_id) && typeof e.actual_summary === 'string') actions.get(e.action_id)!.resultSummary = e.actual_summary
    }
  }
  if (!output) return undefined
  for (const control of output.controlCalls) {
    if (!control.actionId) continue
    const exact = actions.get(control.actionId)?.action
    const execution = exact && [...actions.values()].find(item => item.action.kind === 'execute' && item.action.step_id === exact.step_id && item.action.execution_revision === exact.execution_revision)
    if (execution) bindings.set(control.callId, { actionId: execution.action.id, name: control.name })
  }
  const admittedFrame = (event: EventEnvelope): RecordValue | undefined => {
    const f = event.payload.research_graph_event
    if (!object(f) || typeof f.type !== 'string' || !equal(f.owner, output!.owner) || f.owner && output!.owner.thread_id !== event.threadId || f.attempt_id !== attemptId || f.task_id !== output!.taskId || !checkpointValid(f.checkpoint) || !ref(f.action_id) || !id(f.step_id)) return
    const saved = checkpoints.get(f.checkpoint.ref), execution = actions.get(f.action_id)
    if (!saved || !equal(saved.checkpoint, f.checkpoint) || !execution || execution.action.step_id !== f.step_id ||
      !saved.graph.nodes.some(n => n.id === f.step_id && n.execution_revision === execution.action.execution_revision && (n.execute_action_id === f.action_id || n.assess_action_id === f.action_id))) return
    if (f.type.includes('child') && f.child_id !== f.step_id) return
    return f
  }
  for (const event of eligible) {
    const f = admittedFrame(event)
    if (!f || !enumValue(f.type, ['enterprise_graph_tool_binding', 'enterprise_graph_child_tool']) || !ref(f.tool_call_id) || !text(f.tool_name)) continue
    if (f.type === 'enterprise_graph_child_tool' && !enumValue(f.activity, toolActivities)) continue
    const old = bindings.get(f.tool_call_id)
    if (!old || old.actionId === f.action_id && old.name === f.tool_name) bindings.set(f.tool_call_id, { actionId: String(f.action_id), name: f.tool_name })
  }
  const applyTool = (execution: GraphExecution, call: string, name: string, activity: unknown, event: EventEnvelope, error: unknown, detail: unknown) => {
    if (!enumValue(activity, toolActivities)) return
    let t = execution.tools.find(t => t.id === call)
    if (!t) { t = { id: call, name, status: 'running' }; execution.tools.push(t) }
    const start = ['start', 'tool_execution_start'].includes(activity)
    if (start) t.startedAt ??= event.occurredAt; else t.finishedAt ??= event.occurredAt
    t.status = error === true || t.status === 'failed' ? 'failed' : t.finishedAt ? 'completed' : 'running'
    t.durationMs = elapsed(t.startedAt, t.finishedAt)
    if (object(detail)) { if (typeof detail.operation === 'string') t.operation = detail.operation; if (typeof detail.output_excerpt === 'string') t.output = detail.output_excerpt }
    if (object(detail)&&typeof detail.warning==='string')t.warning=detail.warning.slice(0,241)
    if(error===true&&t.output)t.failure=t.output
  }
  for (const event of eligible) {
    if (event.threadId !== output.owner.thread_id) continue
    const f = admittedFrame(event)
    if (f) {
      const execution = actions.get(String(f.action_id))!
      if (f.type === 'enterprise_graph_child_started') execution.startedAt ??= event.occurredAt
      else if (f.type === 'enterprise_graph_child_finished' && enumValue(f.status, nativeStatuses)) {
        if (execution.finishedAt) continue
        execution.nativeStatus = f.status; execution.finishedAt ??= event.occurredAt; execution.durationMs = elapsed(execution.startedAt, execution.finishedAt)
        if (typeof f.result_summary === 'string') execution.resultSummary = f.result_summary
        if (Number.isSafeInteger(f.model_responses) && Number(f.model_responses) >= 0) execution.modelResponseCount = Number(f.model_responses)
        if (Number.isSafeInteger(f.turns) && Number(f.turns) >= 0) execution.turnCount = Number(f.turns)
      } else if (f.type === 'enterprise_graph_child_response_started' && positive(f.response_number)) {
        const response=execution.responses.find(r => r.number === f.response_number)
        if(response) response.startedAt ??= event.occurredAt
        else execution.responses.push({ number:f.response_number, ms:0, startedAt:event.occurredAt })
      } else if (f.type === 'enterprise_graph_child_response' && positive(f.response_number) && nonnegative(f.response_ms)) {
        let response=execution.responses.find(r => r.number === f.response_number)
        if(!response){response={ number:f.response_number, ms:f.response_ms };execution.responses.push(response)}
        if(!response.finishedAt){
          response.ms=f.response_ms; response.finishedAt=event.occurredAt
          if(object(f.usage))response.usage=f.usage
          if(Array.isArray(f.tool_call_ids)&&f.tool_call_ids.every(ref)&&unique(f.tool_call_ids))response.toolCallIds=f.tool_call_ids
          if(typeof f.response_text==='string')response.responseText=f.response_text
          if(Array.isArray(f.tool_requests)&&f.tool_requests.every(item=>object(item)&&ref(item.id)&&text(item.name)&&(item.operation===undefined||typeof item.operation==='string')))
            response.toolRequests=f.tool_requests as GraphResponse['toolRequests']
          if(enumValue(f.stop_reason,['stop','length','toolUse','error','aborted']))response.stopReason=f.stop_reason
        }
      } else if (f.type === 'enterprise_graph_child_tool' && ref(f.tool_call_id) && text(f.tool_name)) {
        const binding = bindings.get(f.tool_call_id)
        if (binding && binding.actionId === f.action_id && binding.name === f.tool_name) {
          applyTool(execution, f.tool_call_id, f.tool_name, f.activity, event, f.is_error, f.tool_activity)
          if (f.activity === 'end' && nonnegative(f.execution_ms)) execution.tools.find(t => t.id === f.tool_call_id)!.executionMs ??= f.execution_ms
          if(f.activity==='end'&&f.tool_name==='agent_task_return'&&f.is_error===false&&object(f.task_return)
            &&f.task_return.status==='saved'&&Number.isSafeInteger(f.task_return.limitation_count)&&Number(f.task_return.limitation_count)>=0
            &&Array.isArray(f.task_return.limitations)&&f.task_return.limitations.length<=16&&f.task_return.limitations.every(item=>typeof item==='string'))
            execution.tools.find(t=>t.id===f.tool_call_id)!.returnLimitations={count:Number(f.task_return.limitation_count),notes:f.task_return.limitations as string[]}
        }
      }
    }
    const p = event.payload, binding = typeof p.tool_call_id === 'string' ? bindings.get(p.tool_call_id) : undefined
    if (binding && p.task_id === output.taskId && p.tool_name === binding.name && enumValue(p.native_type, ['tool_execution_start', 'tool_execution_end'])) {
      const execution = actions.get(binding.actionId)!
      applyTool(execution, String(p.tool_call_id), binding.name, p.native_type, event, p.is_error, p.activity)
      const control = output.controlCalls.find(item => item.callId === p.tool_call_id), tool = execution.tools.find(item => item.id === p.tool_call_id)
      if (control?.actionId && tool) { tool.actionId = control.actionId; tool.actionKind = actions.get(control.actionId)?.action.kind; tool.origin = 'parent' }
    }
  }
  output.executions = [...actions.values()].filter(e => e.action.kind === 'execute')
  // These are attempt-level observations. They do not establish node ownership.
  const parentResponses: GraphParentResponse[] = [], seen = new Set<string>()
  const starts = new Map<string, EventEnvelope>()
  for (const event of [...events].sort((a, b) => a.eventSeq - b.eventSeq)) {
    if (seen.has(event.eventId) || event.visibility !== 'public' || event.eventType !== 'runtime_action' ||
      event.threadId !== output.owner.thread_id || event.attemptId !== attemptId || event.payload.runtime_mode !== 'capstone') continue
    seen.add(event.eventId)
    const p = event.payload, key = event.turnId ?? ''
    if (p.phase === 'started') {
      starts.delete(key)
      if (p.task_step === undefined && p.task_steps === undefined) starts.set(key, event)
    } else if (p.phase === 'response_completed') {
      const start = starts.get(key), ms = elapsed(start?.occurredAt, event.occurredAt)
      starts.delete(key)
      if (start && ms !== undefined && enumValue(p.response_kind, ['tools', 'text', 'error'])) {
        parentResponses.push({ id: event.eventId, startedAt: start.occurredAt, finishedAt: event.occurredAt, ms, kind: p.response_kind,
          ...(typeof p.error_code==='string'&&/^[a-z][a-z0-9_]{0,127}$/.test(p.error_code)?{errorCode:p.error_code}:{}),
          ...(typeof p.error_status==='number'&&Number.isInteger(p.error_status)&&p.error_status>=400&&p.error_status<=599?{errorStatus:p.error_status}:{}) })
      }
    } else if (p.phase === 'completed') starts.delete(key)
  }
  output.parentResponses = parentResponses
  const pending=[...starts.values()].at(-1)
  if(pending) output.parentPendingResponse={id:pending.eventId,startedAt:pending.occurredAt}
  return output
}
