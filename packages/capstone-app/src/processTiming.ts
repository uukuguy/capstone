/** Observed interval union. Missing timing stays unknown; this is not CPU time. */
export function toolExecutionMs(calls: readonly { startedAt?: string; durationMs?: number }[]): number | undefined {
  if (!calls.length || calls.some(call => !call.startedAt || call.durationMs === undefined)) return undefined
  const spans = calls.map(call => { const start = Date.parse(call.startedAt!); return [start, start + call.durationMs!] }).sort((a, b) => a[0] - b[0])
  if (spans.some(([start, end]) => !Number.isFinite(start) || end < start)) return undefined
  let total = 0, end = -Infinity
  for (const [start, finish] of spans) { total += Math.max(0, finish - Math.max(start, end)); end = Math.max(end, finish) }
  return total
}
