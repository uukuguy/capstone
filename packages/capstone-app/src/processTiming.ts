/** Whole caller-observed batch span, including gaps; no execution-overlap claim. */
export function batchElapsedMs(calls:readonly {startedAt?:string;finishedAt?:string;durationMs?:number;status?:string}[],active=false,now?:number):number|undefined{
  if(!calls.length)return undefined
  const ranges=calls.map(call=>{
    const start=Date.parse(call.startedAt??'')
    const finish=call.finishedAt?Date.parse(call.finishedAt):call.status==='running'
      ?active&&now!==undefined?now:NaN
      :call.durationMs!==undefined&&Number.isFinite(call.durationMs)?start+call.durationMs:NaN
    return {start,finish}
  })
  if(ranges.some(({start,finish})=>!Number.isFinite(start)||!Number.isFinite(finish)||finish<start))return undefined
  return Math.max(...ranges.map(r=>r.finish))-Math.min(...ranges.map(r=>r.start))
}

/** Observed interval union. Missing timing stays unknown; this is not CPU time. */
export function toolExecutionMs(calls: readonly { startedAt?: string; durationMs?: number }[]): number | undefined {
  if (!calls.length || calls.some(call => !call.startedAt || call.durationMs === undefined)) return undefined
  const spans = calls.map(call => { const start = Date.parse(call.startedAt!); return [start, start + call.durationMs!] }).sort((a, b) => a[0] - b[0])
  if (spans.some(([start, end]) => !Number.isFinite(start) || end < start)) return undefined
  let total = 0, end = -Infinity
  for (const [start, finish] of spans) { total += Math.max(0, finish - Math.max(start, end)); end = Math.max(end, finish) }
  return total
}
