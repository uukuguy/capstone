import type {EventEnvelope} from './threadProtocol'

export type ProcessCompaction = {
  id:string; reason:'manual'|'threshold'|'overflow'|'unknown';
  state:'started'|'completed'|'cancelled'|'failed'|'skipped';
  startedAt?:string; finishedAt?:string; elapsedMs?:number; willRetry?:boolean;
}

export function projectProcessCompactions(events:readonly EventEnvelope[],attemptId:string):ProcessCompaction[]{
  const rows:ProcessCompaction[]=[],pending=new Map<string,ProcessCompaction>(),seen=new Set<string>()
  for(const event of [...events].sort((a,b)=>a.eventSeq-b.eventSeq)){
    if(event.attemptId!==attemptId||event.visibility!=='public'||event.eventType!=='runtime_event'||seen.has(event.eventId))continue
    seen.add(event.eventId)
    const phase=event.payload.runtime_phase
    if(event.payload.native_type!=='runtime_phase'||!phase||typeof phase!=='object'||Array.isArray(phase))continue
    const p=phase as Record<string,unknown>
    if(p.name!=='context_compaction'||!['manual','threshold','overflow','unknown'].includes(String(p.reason))||
      !['started','completed','cancelled','failed','skipped'].includes(String(p.state)))continue
    const key=String(event.payload.task_id??'')+':'+String(p.reason)
    const row=p.state==='started'?undefined:pending.get(key)
    const current:ProcessCompaction=row??{id:event.eventId,reason:p.reason as ProcessCompaction['reason'],state:p.state as ProcessCompaction['state']}
    if(!row)rows.push(current)
    if(p.state==='started'){
      current.startedAt=event.occurredAt;pending.set(key,current)
    }else{
      current.state=p.state as ProcessCompaction['state'];current.finishedAt=event.occurredAt
      if(typeof p.elapsed_ms==='number'&&Number.isFinite(p.elapsed_ms)&&p.elapsed_ms>=0)current.elapsedMs=p.elapsed_ms
      if(typeof p.will_retry==='boolean')current.willRetry=p.will_retry
      pending.delete(key)
    }
  }
  return rows
}

export function compactionDuration(phase:ProcessCompaction,active:boolean,now?:number):number|undefined{
  if(phase.elapsedMs!==undefined)return phase.elapsedMs
  const start=Date.parse(phase.startedAt??'')
  const end=phase.finishedAt?Date.parse(phase.finishedAt):active?now:undefined
  return Number.isFinite(start)&&end!==undefined&&Number.isFinite(end)&&end>=start?end-start:undefined
}
