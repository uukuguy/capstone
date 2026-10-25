import {useId,useState} from 'react'
import {ChevronRight} from 'lucide-react'
import MarkdownContent from './MarkdownContent'
import {readProcessStepOpen,saveProcessStepOpen} from './ProcessStepRecord'
import type {EventEnvelope} from './threadProtocol'
import './thinkingProcess.css'

export type InitialThinking={
  text:string;startedAt?:string;endedAt?:string;handedOff:boolean
  phase:'queued'|'running'|'completed'|'failed'|'cancelled'|'interrupted'
}

/** Only supplied public text before the first admitted execution boundary. */
export function projectInitialThinking(events:readonly EventEnvelope[],attemptId:string,handoffSeq?:number):InitialThinking|undefined {
  const current=events.filter(event=>event.visibility==='public'&&(event.attemptId===attemptId||(!event.attemptId&&event.turnId===attemptId)))
  const begin=current.find(event=>['command_accepted','attempt_started','assistant_thinking_delta','runtime_action'].includes(event.eventType))
  if(!begin)return
  const terminal=current.find(event=>['attempt_completed','attempt_failed','attempt_cancelled','attempt_interrupted'].includes(event.eventType))
  const handoff=handoffSeq===undefined?undefined:current.find(event=>event.eventSeq===handoffSeq)
  const seen=new Set<string>()
  let text=''
  for(const event of current) {
    if(event.eventType!=='assistant_thinking_delta'||event.attemptId!==attemptId||typeof event.payload.text!=='string'||
      (handoffSeq!==undefined&&event.eventSeq>=handoffSeq)||(terminal&&event.eventSeq>=terminal.eventSeq)||seen.has(event.eventId))continue
    seen.add(event.eventId);text+=event.payload.text
  }
  const phase=terminal?terminal.eventType.slice('attempt_'.length) as InitialThinking['phase']:
    current.some(event=>event.eventType==='attempt_started'||event.eventType==='assistant_thinking_delta'||event.eventType==='runtime_action')?'running':'queued'
  return {text,startedAt:begin.occurredAt,endedAt:handoff?.occurredAt??terminal?.occurredAt,handedOff:Boolean(handoff),phase}
}

/** Initial phase only. Later model calls remain in their task/tool process. */
export default function ThinkingProcess({thinking,storageKey,now=Date.now(),expanded=false}:{thinking:InitialThinking;storageKey:string;now?:number;expanded?:boolean}) {
  const bodyId=useId()
  const active=!thinking.handedOff&&['queued','running'].includes(thinking.phase)
  const foldId=`thinking:${thinking.handedOff?'archive':'initial'}:${active?'active':thinking.phase}${expanded?':reader':''}`
  const fallback=active||expanded
  const [fold,setFold]=useState(()=>({id:foldId,open:readProcessStepOpen(storageKey,foldId,fallback)}))
  const open=fold.id===foldId?fold.open:readProcessStepOpen(storageKey,foldId,fallback)
  const status=thinking.phase==='failed'?'本轮失败':thinking.phase==='cancelled'?'本轮已取消':thinking.phase==='interrupted'?'本轮已中断':
    thinking.handedOff?'已转入执行过程':thinking.phase==='completed'?'已结束':thinking.phase==='queued'?'已提交，等待执行':thinking.text?'正在思考':'等待模型进展'
  const start=Date.parse(thinking.startedAt??''),end=thinking.endedAt?Date.parse(thinking.endedAt):now
  const elapsed=Number.isFinite(start)&&Number.isFinite(end)&&end>=start?((end-start)/1000).toFixed(1):undefined
  return <section className="capstone-thinking-process" role="region" aria-label={thinking.handedOff?'初始思考记录':'思考状态'} data-phase={thinking.phase} aria-busy={active}>
    <div className="capstone-process-step-heading">
      <button type="button" className="capstone-process-step-toggle" aria-label={`${open?'折叠':'展开'}初始思考`} aria-expanded={open} aria-controls={bodyId} onClick={()=>{
        setFold({id:foldId,open:!open});saveProcessStepOpen(storageKey,foldId,!open)
      }}><ChevronRight aria-hidden="true"/></button>
      <strong>思考</strong><span className="capstone-thinking-status">{status}</span>
      {elapsed!==undefined&&<small>{active?'已用时':'用时'} {elapsed}s</small>}
    </div>
    {open&&<div id={bodyId} className="capstone-thinking-copy">
      {thinking.text?<MarkdownContent>{thinking.text}</MarkdownContent>:<p className="capstone-task-goal">当前记录未提供公开思考摘要。</p>}
    </div>}
  </section>
}
