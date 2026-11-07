export type ToolExecutionEvent = { phase: string; at: string; elapsed_ms: number; provenance: 'owner_scheduler' | 'authority_process' }
export type ToolExecutionReceipt = { schema: 'capstone-tool-execution/1'; owner_id: string; scope_id: string; task_id: string; call_id: string; policy_version: string; capacity: number; events: ToolExecutionEvent[] }
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)
const identity = (value: unknown): value is string => typeof value === 'string' && value.length > 0 && value.length <= 256 && value.trim() === value && !/[\u0000-\u001f\u007f]/.test(value)
const phases = ['submitted', 'queued', 'acquired', 'execution_started', 'execution_ended', 'released']
/** Reject unrelated, malformed and non-monotonic owner observations. */
export function parseToolExecutionReceipt(value: unknown, callId: string): ToolExecutionReceipt | undefined {
  if (!object(value) || value.schema !== 'capstone-tool-execution/1' || value.call_id !== callId
    || !['owner_id', 'scope_id', 'task_id', 'call_id', 'policy_version'].every(key => identity(value[key]))
    || !Number.isSafeInteger(value.capacity) || Number(value.capacity) < 1 || Number(value.capacity) > 1024 || !Array.isArray(value.events) || !value.events.length || value.events.length > phases.length) return
  let previous = -1, elapsed = -1
  for (const event of value.events) {
    if (!object(event) || typeof event.phase !== 'string' || phases.indexOf(event.phase) <= previous
      || typeof event.at !== 'string' || !Number.isFinite(Date.parse(event.at))
      || typeof event.elapsed_ms !== 'number' || !Number.isFinite(event.elapsed_ms) || event.elapsed_ms < 0 || event.elapsed_ms < elapsed
      || event.provenance !== (event.phase.startsWith('execution_') ? 'authority_process' : 'owner_scheduler')) return
    previous = phases.indexOf(event.phase); elapsed = event.elapsed_ms
  }
  return { schema: value.schema, owner_id: String(value.owner_id), scope_id: String(value.scope_id), task_id: String(value.task_id), call_id: String(value.call_id), policy_version: String(value.policy_version), capacity: Number(value.capacity), events: value.events.map(event => ({phase:event.phase,at:event.at,elapsed_ms:event.elapsed_ms,provenance:event.provenance})) }
}
export function receiptDuration(receipt: ToolExecutionReceipt | undefined, start: string, end: string) {
  const a = receipt?.events.find(event => event.phase === start), b = receipt?.events.find(event => event.phase === end)
  return a && b ? b.elapsed_ms - a.elapsed_ms : undefined
}
/** Only one owner clock and fully recorded intervals support an exact batch peak. */
export function receiptBatchSummary(receipts: readonly (ToolExecutionReceipt | undefined)[]) {
  const first = receipts[0]
  if (!first || receipts.some(receipt => !receipt || receipt.owner_id !== first.owner_id || receipt.scope_id !== first.scope_id || receipt.capacity !== first.capacity || receipt.policy_version !== first.policy_version)) return {}
  const known = receipts as readonly ToolExecutionReceipt[]
  const ranges = known.map(receipt => ({ start: receipt.events.find(event => event.phase === 'execution_started')?.elapsed_ms, end: receipt.events.find(event => event.phase === 'execution_ended')?.elapsed_ms }))
  if (ranges.some(range => range.start === undefined || range.end === undefined)) return { capacity: first.capacity }
  const points = ranges.flatMap(range => range.end! > range.start! ? [[range.start!, 1], [range.end!, -1]] : []).sort((a,b) => a[0]-b[0] || a[1]-b[1])
  let active = 0, peak = 0
  for (const [,delta] of points) { active += delta; peak = Math.max(active, peak) }
  const submitted = known.map(receipt => receipt.events.find(event => event.phase === 'submitted')?.elapsed_ms)
  return { capacity: first.capacity, peak, elapsedMs: submitted.every(value => value !== undefined) ? Math.max(...ranges.map(range => range.end!)) - Math.min(...submitted as number[]) : undefined }
}
