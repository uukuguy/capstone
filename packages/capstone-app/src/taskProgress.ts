import { parseResearchSnapshot } from './ResearchEvidence'
import type { EventEnvelope } from './threadProtocol'

export type TaskProgress = { id: string; text: string; refs: string[]; revision: number; sequence: number }

// Project committed public work records. Do not invent a stage from tool names.
export function projectTaskProgress(events: readonly EventEnvelope[], attemptId: string): TaskProgress[] {
  const previous = new Map<string, { text: string; refs: string[]; id?: string }>()
  const revisions = new Map<string, number>()
  const output: TaskProgress[] = []
  for (const event of events) {
    if (event.eventType !== 'research_state_updated') continue
    const snapshot = parseResearchSnapshot(event.payload.research_snapshot)
    if (!snapshot || snapshot.research_id !== event.payload.research_id ||
      snapshot.revision !== event.payload.research_revision || snapshot.goal !== event.payload.goal ||
      snapshot.revision <= (revisions.get(snapshot.research_id) ?? 0)) continue
    revisions.set(snapshot.research_id, snapshot.revision)
    const noteIds = event.payload.current_note_ids
    const currentIds = Array.isArray(noteIds) && noteIds.length <= 64 &&
      noteIds.every(id => typeof id === 'string' && snapshot.notes.some(note => note.note_id === id)) &&
      new Set(noteIds).size === noteIds.length ? new Set(noteIds) : new Set<string>()
    for (const note of snapshot.notes) {
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
