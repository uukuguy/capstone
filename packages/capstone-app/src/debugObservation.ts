import type {AttemptRecordReader} from './AttemptRecordPanel'

const observations=new Map([
  ['tool_failed','工具调用失败'],
  ['validation_failed','核验失败'],
  ['attempt_interrupted','任务中断'],
  ['attempt_failed','任务失败'],
])

export async function firstDebugObservation(attempt:string,read:AttemptRecordReader,through:number){
  let after=0
  while(after<through){
    const page=await read(attempt,after)
    for(const event of page.events){
      if(event.eventSeq>through)break
      const label=event.eventType==='validation_observation'&&event.payload?.status==='failed'
        ?'核验失败':observations.get(event.eventType)
      if(event.visibility==='public'&&label)return {seq:event.eventSeq,label}
    }
    if(!page.hasMore)break
    if(page.nextAfter<=after)throw new Error('执行记录游标无效。')
    after=page.nextAfter
  }
  return null
}
