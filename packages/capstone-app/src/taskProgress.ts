import {exceedsCapacity} from './applicationCapacity'
import { parseResearchSnapshot } from './ResearchEvidence'
import type { EventEnvelope } from './threadProtocol'

export type TaskProgress = { id: string; text: string; refs: string[]; revision?: number; sequence: number; kind?: 'goal' | 'observation' | 'adjustment' | 'limitation'; stepId?: string; phase?: string }
export type TaskStepDiagnostic = { id: string; text: string }
export type ResearchBranch = {
  id: string; parentStepId: string; title: string; questions: string[]; expectedOutputs: string[];
  status: 'running' | 'completed' | 'failed' | 'cancelled' | 'unknown'; resultSummary?: string; error?: string;
  startedAt?: string; finishedAt?: string; durationMs?: number;
  responses?: Record<string, number>;
  tools: { id: string; name: string; status: 'running' | 'completed' | 'failed'; operation?: string; output?: string }[];
}

export function projectResearchBranches(events: readonly EventEnvelope[], attemptId: string): ResearchBranch[] {
  const branches = new Map<string, ResearchBranch>()
  const object = (value: unknown): value is Record<string, unknown> => Boolean(value && typeof value === 'object' && !Array.isArray(value))
  const text = (value: unknown): value is string => typeof value === 'string' && value.trim().length > 0 && !exceedsCapacity(value.length, 'research_text_chars')
  const texts = (value: unknown): value is string[] => Array.isArray(value) && !exceedsCapacity(value.length, 'research_question_count') && value.every(text)
  for (const event of events) {
    if (event.visibility !== 'public' || event.eventType !== 'runtime_event' || event.attemptId !== attemptId) continue
    const record = event.payload.research_branch
    if (!object(record) || record.subordinate !== true || record.attempt_id !== attemptId || !object(record.owner) ||
      record.owner.thread_id !== event.threadId || !text(record.parent_tool_call_id) || !text(record.child_id) ||
      !text(record.title) || !text(record.parent_step_id) || !text(record.parent_action_id) ||
      !object(record.checkpoint) || !text(record.checkpoint.ref) || !Number.isSafeInteger(record.checkpoint.revision) || Number(record.checkpoint.revision) < 1 ||
      !texts(record.questions) || !texts(record.expected_outputs)) continue
    if (!['delegation_child_started', 'delegation_child_tool', 'delegation_child_finished', 'delegation_child_response'].includes(String(record.type))) continue
    const id = JSON.stringify([event.threadId, attemptId, record.parent_tool_call_id, record.child_id])
    const previous = branches.get(id)
    if (previous && previous.parentStepId !== record.parent_step_id) continue
    const branch: ResearchBranch = { id, parentStepId: record.parent_step_id, title: record.title,
      questions: record.questions, expectedOutputs: record.expected_outputs,
      status: previous?.status ?? 'running', tools: [...(previous?.tools ?? [])],
      startedAt: previous?.startedAt, finishedAt: previous?.finishedAt, durationMs: previous?.durationMs,
      responses: previous?.responses,
      ...(previous?.resultSummary ? { resultSummary: previous.resultSummary } : {}),
      ...(previous?.error ? { error: previous.error } : {}) }
    if (record.type === 'delegation_child_started' && !branch.startedAt && Number.isFinite(Date.parse(event.occurredAt))) {
      branch.startedAt = event.occurredAt
    } else if (record.type === 'delegation_child_response') {
      if (!Number.isSafeInteger(record.response_number) || Number(record.response_number) < 1 || !Number.isSafeInteger(record.response_ms) || Number(record.response_ms) < 0) continue
      branch.responses = { ...previous?.responses, [String(record.response_number)]: Number(record.response_ms) }
    } else if (record.type === 'delegation_child_finished') {
      if (!['completed', 'failed', 'cancelled'].includes(String(record.status))) continue
      branch.status = record.status as ResearchBranch['status']
      if (Number.isFinite(Date.parse(event.occurredAt))) {
        branch.finishedAt = event.occurredAt
        const start = branch.startedAt ? Date.parse(branch.startedAt) : NaN
        const end = Date.parse(event.occurredAt)
        if (Number.isFinite(start) && end >= start) branch.durationMs = end - start
      }
      if (text(record.result_summary)) branch.resultSummary = record.result_summary
      if (object(record.error) && text(record.error.message)) branch.error = record.error.message
    } else if (record.type === 'delegation_child_tool') {
      if (!text(record.tool_call_id) || !text(record.tool_name) || !['start', 'end', 'tool_execution_start', 'tool_execution_end'].includes(String(record.activity))) continue
      const prior = branch.tools.find(tool => tool.id === record.tool_call_id)
      const tool: ResearchBranch['tools'][number] = { id: record.tool_call_id, name: record.tool_name,
        status: prior?.status === 'failed' || record.is_error === true ? 'failed' : prior?.status === 'completed' || ['end', 'tool_execution_end'].includes(String(record.activity)) ? 'completed' : 'running',
        operation: prior?.operation, output: prior?.output }
      if (object(record.tool_activity)) {
        if (text(record.tool_activity.operation)) tool.operation = record.tool_activity.operation
        if (text(record.tool_activity.output_excerpt)) tool.output = record.tool_activity.output_excerpt
      }
      branch.tools = [...branch.tools.filter(item => item.id !== tool.id), tool]
    }
    branches.set(id, branch)
  }
  if (events.some(event => event.attemptId === attemptId && ['attempt_completed', 'attempt_failed', 'attempt_cancelled', 'attempt_interrupted'].includes(event.eventType))) {
    for (const branch of branches.values()) if (branch.status === 'running') branch.status = 'unknown'
  }
  return [...branches.values()]
}

export function projectTaskStepDiagnostics(events: readonly EventEnvelope[], attemptId: string): TaskStepDiagnostic[] {
  return events.flatMap(event => event.visibility === 'public' && event.attemptId === attemptId &&
    typeof event.payload.task_step_error === 'string' && event.payload.task_step_error.trim().length > 0 &&
    !exceedsCapacity(event.payload.task_step_error.length, 'research_progress_chars')
    ? [{ id: event.eventId, text: event.payload.task_step_error }] : [])
}

// Project committed public work records. Do not invent a stage from tool names.
export function projectTaskProgress(events: readonly EventEnvelope[], attemptId: string): TaskProgress[] {
  const previous = new Map<string, { text: string; refs: string[]; id?: string }>()
  const revisions = new Map<string, number>()
  const output: TaskProgress[] = []
  for (const event of events) {
    const nativeProgress=event.eventType==='runtime_event'&&event.payload.native_type==='tool_execution_end'
      &&event.payload.tool_name==='agent_task_progress'&&event.payload.is_error===false
    if (event.visibility==='public' && event.attemptId === attemptId && (nativeProgress ||
      event.eventType === 'tool_completed' && event.payload.capability === 'agent_task_progress' && event.payload.ok === true)) {
      const value = event.payload.task_progress
      if (value && typeof value === 'object' && !Array.isArray(value)) {
        const record = value as Record<string, unknown>
        if (typeof record.kind === 'string' && ['goal', 'observation', 'adjustment', 'limitation'].includes(record.kind) &&
          typeof record.text === 'string' && record.text.length > 0 && !exceedsCapacity(record.text.length,'research_text_chars') &&
          Array.isArray(record.refs) && !exceedsCapacity(record.refs.length,'context_references') &&
          record.refs.every(ref => typeof ref === 'string' && ref.length > 0 && ref.length <= 256)) {
          output.push({ id: event.eventId, text: record.text, refs: record.refs as string[],
            kind: record.kind as TaskProgress['kind'], sequence: event.eventSeq,
            ...(event.payload.runtime_step_tracking === true
              ? typeof event.payload.task_step_id === 'string' ? { stepId: event.payload.task_step_id } : {}
              : typeof record.step_id === 'string' ? { stepId: record.step_id } : {}),
            ...(typeof record.phase === 'string' ? { phase: record.phase } : {}) })
        }
      }
      continue
    }
    if (event.eventType !== 'research_state_updated') continue
    const snapshot = parseResearchSnapshot(event.payload.research_snapshot)
    if (!snapshot || snapshot.research_id !== event.payload.research_id ||
      snapshot.revision !== event.payload.research_revision || snapshot.goal !== event.payload.goal ||
      snapshot.revision <= (revisions.get(snapshot.research_id) ?? 0)) continue
    revisions.set(snapshot.research_id, snapshot.revision)
    const noteIds = event.payload.current_note_ids
    const currentIds = Array.isArray(noteIds) && !exceedsCapacity(noteIds.length,'research_note_count') &&
      noteIds.every(id => typeof id === 'string' && snapshot.notes.some(note => note.note_id === id)) &&
      new Set(noteIds).size === noteIds.length ? new Set(noteIds) : new Set<string>()
    for (const note of snapshot.notes) {
      // Older event pages can contain host recovery notes. Keep them out of
      // reader-facing progress when replaying those retained records.
      if (note.note_id.startsWith('runtime.checkpoint.') || note.note_id.startsWith('runtime.dispatch.')) continue
      const key = `${snapshot.research_id}:${note.note_id}`
      const before = previous.get(key)
      const changed = !before || before.text !== note.text || JSON.stringify(before.refs) !== JSON.stringify(note.refs)
      if (!changed) continue
      const id = `${event.eventId}:${note.note_id}`
      const owned = event.attemptId === attemptId && currentIds.has(note.note_id)
      if (owned) output.push({ id, text: note.text, refs: note.refs, revision: snapshot.revision,
        sequence: event.eventSeq })
      previous.set(key, { text: note.text, refs: note.refs, ...(owned ? { id } : {}) })
    }
  }
  return output
}
