import {expect,it} from 'vitest'
import {projectProcessCompactions,compactionDuration} from './processCompactions'
import {projectProcessModelRequests} from './processModelRequests'
import type {EventEnvelope} from './threadProtocol'

const event=(seq:number,state:string,task='native'):EventEnvelope=>({eventId:`e${seq}`,eventSeq:seq,eventVersion:1,
 eventType:'runtime_event',threadId:'thread',runId:'run',attemptId:'attempt',visibility:'public',
 occurredAt:`2026-11-01T00:00:0${seq}Z`,payload:{native_type:'runtime_phase',task_id:task,
 runtime_phase:{name:'context_compaction',state,reason:'threshold',...(state==='started'?{}:{elapsed_ms:16081,will_retry:false}),summary:'PRIVATE'}}})

it('pairs by native task, deduplicates replay and preserves host duration without creating model calls',()=>{
 const start=event(1,'started'),other=event(2,'started','other'),end=event(3,'completed')
 const events=[end,start,other,start,{...event(4,'failed'),attemptId:'old'}]
 const phases=projectProcessCompactions(events,'attempt')
 expect(phases).toHaveLength(2)
 expect(phases[0]).toMatchObject({state:'completed',elapsedMs:16081,startedAt:start.occurredAt,finishedAt:end.occurredAt})
 expect(phases[1].state).toBe('started')
 expect(JSON.stringify(phases)).not.toContain('PRIVATE')
 expect(projectProcessModelRequests(events,'attempt')).toHaveLength(0)
 expect(compactionDuration(phases[0],false)).toBe(16081)
 expect(compactionDuration(phases[1],true,Date.parse(other.occurredAt)+2500)).toBe(2500)
 expect(compactionDuration(phases[1],false,Date.now())).toBeUndefined()
})

it('retains terminal-only records and rejects invalid or unrelated phase payloads',()=>{
 const orphan=event(1,'failed'),invalid=event(2,'invented'),privateEvent={...event(3,'started'),visibility:'diagnostic' as const}
 const phases=projectProcessCompactions([orphan,invalid,privateEvent],'attempt')
 expect(phases).toHaveLength(1);expect(phases[0].startedAt).toBeUndefined();expect(phases[0].state).toBe('failed')
})
