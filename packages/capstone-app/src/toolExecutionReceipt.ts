export type ToolExecutionEvent = { phase: string; at: string; elapsed_ms: number; provenance: 'owner_scheduler' | 'authority_process' }
export type ToolExecutionReceipt = { schema: 'capstone-tool-execution/1'; owner_id: string; scope_id: string; task_id: string; call_id: string; policy_version: string; capacity: number; events: ToolExecutionEvent[] }
export type ToolDispatchReceipt = Omit<ToolExecutionReceipt, 'schema' | 'events'> & {schema:'capstone-tool-dispatch/1'; events:{phase:string;at:string;elapsed_ms:number;provenance:'native_dispatch'}[]}
export type ToolBatch = {schema:'capstone-tool-batch/1';task_id:string;batch_id:string;mode:'parallel';capacity:number;call_ids:string[];elapsed_ms:number}
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)
const identity = (value: unknown): value is string => typeof value === 'string' && value.length > 0 && value.length <= 256 && value.trim() === value && !/[\u0000-\u001f\u007f]/.test(value)
const phases = ['submitted', 'queued', 'acquired', 'execution_started', 'execution_ended', 'released']
export function parseToolBatch(value:unknown,taskId:string):ToolBatch|undefined{
  if(!object(value)||value.schema!=='capstone-tool-batch/1'||value.task_id!==taskId||value.mode!=='parallel'||!identity(value.batch_id)||!Array.isArray(value.call_ids)||!value.call_ids.length||value.call_ids.length>1024||!value.call_ids.every(identity)||new Set(value.call_ids).size!==value.call_ids.length||!Number.isSafeInteger(value.capacity)||Number(value.capacity)<1||Number(value.capacity)>1024||typeof value.elapsed_ms!=='number'||!Number.isFinite(value.elapsed_ms)||value.elapsed_ms<0)return
  return {schema:value.schema,task_id:taskId,batch_id:value.batch_id,mode:value.mode,capacity:Number(value.capacity),call_ids:[...value.call_ids],elapsed_ms:value.elapsed_ms}
}
export function dispatchDuration(receipt:ToolDispatchReceipt|undefined){
  const start=receipt?.events.find(event=>event.phase==='invocation_started')?.elapsed_ms
  const end=receipt?.events.find(event=>event.phase==='invocation_settled')?.elapsed_ms
  return start!==undefined&&end!==undefined?end-start:undefined
}
/** Native invocation boundaries are separate from Authority process evidence. */
export function parseToolDispatchReceipt(value: unknown, callId: string): ToolDispatchReceipt | undefined {
  if(!object(value)||value.schema!=='capstone-tool-dispatch/1'||value.scope_id!==value.task_id||!Array.isArray(value.events))return
  const converted={...value,schema:'capstone-tool-execution/1',events:value.events.map(event=>{
    if(!object(event)||event.provenance!=='native_dispatch')return null
    const phase=event.phase==='invocation_started'?'execution_started':event.phase==='invocation_settled'?'execution_ended':event.phase
    if(!phases.includes(String(phase)))return null
    return {...event,phase,provenance:String(phase).startsWith('execution_')?'authority_process':'owner_scheduler'}
  })}
  const checked=parseToolExecutionReceipt(converted,callId)
  if(!checked)return
  return {...checked,schema:'capstone-tool-dispatch/1',events:checked.events.map(event=>({...event,phase:event.phase==='execution_started'?'invocation_started':event.phase==='execution_ended'?'invocation_settled':event.phase,provenance:'native_dispatch'}))}
}
export function dispatchBatchSummary(receipts: readonly (ToolDispatchReceipt | undefined)[]) {
  const first=receipts[0]
  if(!first||receipts.some(receipt=>!receipt||receipt.owner_id!==first.owner_id||receipt.scope_id!==first.scope_id||receipt.capacity!==first.capacity||receipt.policy_version!==first.policy_version))return {}
  const known=receipts as readonly ToolDispatchReceipt[]
  const starts=known.map(receipt=>receipt.events.find(event=>event.phase==='submitted')?.elapsed_ms)
  const ends=known.map(receipt=>receipt.events.find(event=>event.phase==='released')?.elapsed_ms)
  return {capacity:first.capacity,elapsedMs:starts.every(value=>value!==undefined)&&ends.every(value=>value!==undefined)?Math.max(...ends as number[])-Math.min(...starts as number[]):undefined}
}
/** Reject unrelated, malformed and non-monotonic owner observations. */
export function parseToolExecutionReceipt(value: unknown, callId: string): ToolExecutionReceipt | undefined {
  if (!object(value) || value.schema !== 'capstone-tool-execution/1' || value.call_id !== callId
    || !['owner_id', 'scope_id', 'task_id', 'call_id', 'policy_version'].every(key => identity(value[key]))
    || !Number.isSafeInteger(value.capacity) || Number(value.capacity) < 1 || Number(value.capacity) > 1024 || !Array.isArray(value.events) || !value.events.length || value.events.length > phases.length + 1) return
  let previous = -1, elapsed = -1
  const seen = new Set<string>()
  for (const event of value.events) {
    if (!object(event) || typeof event.phase !== 'string' || seen.has(event.phase)
      || (event.phase === 'cancellation_requested' ? !seen.has('queued') || seen.has('released') : phases.indexOf(event.phase) <= previous)
      || typeof event.at !== 'string' || !Number.isFinite(Date.parse(event.at))
      || typeof event.elapsed_ms !== 'number' || !Number.isFinite(event.elapsed_ms) || event.elapsed_ms < 0 || event.elapsed_ms < elapsed
      || event.provenance !== (event.phase.startsWith('execution_') ? 'authority_process' : 'owner_scheduler')) return
    if (event.phase === 'execution_started' && !seen.has('acquired')
      || event.phase === 'execution_ended' && !seen.has('execution_started')
      || event.phase === 'released' && seen.has('execution_started') && !seen.has('execution_ended')) return
    if (event.phase !== 'cancellation_requested') previous = phases.indexOf(event.phase)
    seen.add(event.phase); elapsed = event.elapsed_ms
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
