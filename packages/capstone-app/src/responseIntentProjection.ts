import type {EventEnvelope} from './threadProtocol'
import {responseOpeningIntent} from './executionIntent'
import {isExecutionLifecycleStep} from './executionLifecycle'

/** Retain only explicit opening comments before diagnostic deltas are evicted. */
export class ResponseIntentProjection {
  private rows=new Map<string,{text:string;lastSeq:number;closed:boolean}>()
  clear(){this.rows.clear()}
  observe(events:readonly EventEnvelope[]){
    const active=new Map<string,string>(),retained=new Set<string>()
    for(const event of events){
      const key=event.attemptId
      if(!key)continue
      if(event.eventType==='runtime_action'&&event.visibility==='public'){
        if(event.payload.phase==='started'){
          const step=event.payload.task_step as {id?:string}|undefined
          if(step?.id&&isExecutionLifecycleStep(step.id)){active.delete(key);continue}
          active.set(key,event.eventId);retained.add(event.eventId)
          if(!this.rows.has(event.eventId))this.rows.set(event.eventId,{text:'',lastSeq:event.eventSeq,closed:false})
        }else if(['response_completed','completed','interrupted'].includes(String(event.payload.phase)))active.delete(key)
      }else if(event.eventType==='assistant_process_delta'&&typeof event.payload.text==='string'){
        const id=active.get(key),row=id?this.rows.get(id):undefined
        if(row&&!row.closed&&event.eventSeq>row.lastSeq){
          row.text=(row.text+event.payload.text).slice(0,512).split(/\r?\n/,1)[0]
          row.lastSeq=event.eventSeq
          row.closed=/[\r\n]/.test(event.payload.text)||row.text.length>=512
        }
      }
    }
    for(const id of this.rows.keys())if(!retained.has(id))this.rows.delete(id)
  }
  intent(id:string){
    const value=responseOpeningIntent(this.rows.get(id)?.text)
    return value&&!/(?:api[_ -]?key|access[_ -]?token|authorization|password|secret)["']?\s*[:=]/i.test(value)?value:undefined
  }
}
