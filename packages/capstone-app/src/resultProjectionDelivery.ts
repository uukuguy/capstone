import { parseResultProjection, type EventEnvelope } from './threadProtocol'

const MAX_BYTES = 8 * 1024 * 1024
const MAX_PARTS = Math.ceil(MAX_BYTES / 4000)

type Parts = { event: EventEnvelope; count: number; data: string[] }

/** Reassemble only the parts named by an admitted terminal event. */
export class ResultProjectionDelivery {
  private readonly entries = new Map<string, Parts>()
  private bytes = 0

  clear(): void {
    this.entries.clear()
    this.bytes = 0
  }

  accept(event: EventEnvelope): void {
    if (event.eventType !== 'result_projection_part') return
    const { result_id: id, part_index: index, parts: count, data } = event.payload
    if (typeof id !== 'string' || !/^[a-zA-Z0-9_.:-]{1,128}$/.test(id) || !event.attemptId || !Number.isInteger(index) || !Number.isInteger(count) ||
      typeof index !== 'number' || typeof count !== 'number' || count < 1 || count > MAX_PARTS ||
      typeof data !== 'string' || !data || Array.from(data).length > 4000) throw new Error('result projection part is invalid')
    const key = `${event.attemptId}:${id}`
    const entry = this.entries.get(key) ?? { event, count, data: [] }
    if (count !== entry.count || index !== entry.data.length || index >= count ||
      !sameAttempt(entry.event, event)) throw new Error('result projection parts do not match')
    const size = new TextEncoder().encode(data).byteLength
    if (this.bytes + size > MAX_BYTES) throw new Error('result projection parts exceed the size limit')
    entry.data.push(data)
    this.entries.set(key, entry)
    this.bytes += size
  }

  complete(event: EventEnvelope): Record<string, unknown>[] | undefined {
    const manifest = event.payload.result_projection_manifest
    if (manifest === undefined) return undefined
    const admission = event.payload.admission as Record<string, unknown> | undefined
    if (!['attempt_completed', 'attempt_failed'].includes(event.eventType) || !Array.isArray(manifest) ||
      manifest.length > 64 || admission?.mode !== 'authority_backed' || admission.assurance !== 'lineage_verified') {
      throw new Error('result projection manifest is invalid')
    }
    const ids = new Set<string>()
    const documents = manifest.map((item) => {
      if (!item || typeof item !== 'object' || typeof item.result_id !== 'string' || ids.has(item.result_id)) {
        throw new Error('result projection manifest identity is invalid')
      }
      ids.add(item.result_id)
      const entry = this.entries.get(`${event.attemptId}:${item.result_id}`)
      if (!entry || entry.count !== item.parts || entry.data.length !== entry.count ||
        !sameAttempt(entry.event, event)) throw new Error('result projection delivery is incomplete')
      const document = JSON.parse(entry.data.join('')) as Record<string, unknown>
      const projection = parseResultProjection(document)
      if (projection.resultId !== item.result_id || projection.threadId !== event.threadId ||
        projection.runId !== event.runId || projection.turnId !== event.turnId ||
        projection.attemptId !== event.attemptId || projection.modelContextId !== event.modelContextId ||
        !Array.isArray(event.payload.result_refs) || !event.payload.result_refs.includes(projection.resultRef) ||
        !Array.isArray(event.payload.evidence_refs) ||
        projection.evidenceRefs.some((ref) => !(event.payload.evidence_refs as unknown[]).includes(ref))) {
        throw new Error('result projection delivery does not match admission')
      }
      return document
    })
    this.clear()
    return documents
  }
}

function sameAttempt(first: EventEnvelope, second: EventEnvelope): boolean {
  return first.threadId === second.threadId && first.runId === second.runId && first.turnId === second.turnId &&
    first.attemptId === second.attemptId && first.modelContextId === second.modelContextId &&
    first.selectionRevision === second.selectionRevision
}
