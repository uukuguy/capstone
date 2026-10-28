import {useId,useLayoutEffect,useRef,useState} from 'react'
import {ChevronRight} from 'lucide-react'
import MarkdownContent from './MarkdownContent'
import {readProcessStepOpen,saveProcessStepOpen} from './ProcessStepRecord'
import type {EventEnvelope} from './threadProtocol'
import './thinkingProcess.css'

export type InitialThinking={
  text:string;continuationText?:string;startedAt?:string;endedAt?:string;handedOff:boolean
  phase:'queued'|'running'|'completed'|'failed'|'cancelled'|'interrupted'
}

/** Public lightweight-loop text, retained until terminal or admitted task handoff. */
export function projectInitialThinking(events:readonly EventEnvelope[],attemptId:string,handoffSeq?:number,retainUntilSeq=handoffSeq):InitialThinking|undefined {
  const current=events.filter(event=>event.visibility==='public'&&(event.attemptId===attemptId||(!event.attemptId&&event.turnId===attemptId)))
  const begin=current.find(event=>event.eventType==='attempt_started')??current.find(event=>['command_accepted','assistant_thinking_delta','runtime_action'].includes(event.eventType))
  if(!begin)return
  const terminal=current.find(event=>['attempt_completed','attempt_failed','attempt_cancelled','attempt_interrupted'].includes(event.eventType))
  const handoff=handoffSeq===undefined?undefined:current.find(event=>event.eventSeq===handoffSeq)
  const seen=new Set<string>()
  let text='',continuationText=''
  for(const event of current) {
    if(event.eventType!=='assistant_thinking_delta'||event.attemptId!==attemptId||typeof event.payload.text!=='string'||
      (retainUntilSeq!==undefined&&event.eventSeq>=retainUntilSeq)||(terminal&&event.eventSeq>=terminal.eventSeq)||seen.has(event.eventId))continue
    seen.add(event.eventId)
    if(handoffSeq!==undefined&&event.eventSeq>=handoffSeq)continuationText+=event.payload.text
    else text+=event.payload.text
  }
  const phase=terminal?terminal.eventType.slice('attempt_'.length) as InitialThinking['phase']:
    current.some(event=>event.eventType==='attempt_started'||event.eventType==='assistant_thinking_delta'||event.eventType==='runtime_action')?'running':'queued'
  return {text,...(continuationText?{continuationText}:{}),startedAt:begin.occurredAt,endedAt:handoff?.occurredAt??terminal?.occurredAt,handedOff:Boolean(handoff),phase}
}

/** Lightweight thinking stays above the answer; admitted tasks own later thinking. */
export default function ThinkingProcess({thinking,storageKey,now=Date.now(),expanded=false,kind='initial'}:{thinking:InitialThinking;storageKey:string;now?:number;expanded?:boolean;kind?:'initial'|'call'}) {
  const bodyId=useId()
  const active=!thinking.handedOff&&['queued','running'].includes(thinking.phase)
  const foldId=`thinking:${thinking.handedOff?'archive':'initial'}:${active?'active':thinking.phase}${expanded?':reader':''}`
  const fallback=active
  const [fold,setFold]=useState(()=>({id:foldId,open:readProcessStepOpen(storageKey,foldId,fallback)}))
  const open=fold.id===foldId?fold.open:readProcessStepOpen(storageKey,foldId,fallback)
  const start=Date.parse(thinking.startedAt??''),end=thinking.endedAt?Date.parse(thinking.endedAt):now
  const elapsed=Number.isFinite(start)&&Number.isFinite(end)&&end>=start?(end-start)/1000:undefined
  const status=thinking.phase==='failed'?'思考已停止（本轮失败）':thinking.phase==='cancelled'?'思考已取消':thinking.phase==='interrupted'?'思考已中断':
    active?thinking.phase==='queued'?'等待执行…':'思考中…':elapsed===undefined?'已思考':`已思考 ${Math.round(elapsed)}秒`
  const viewport=useRef<HTMLDivElement>(null),following=useRef(true)
  useLayoutEffect(()=>{
    if(active&&open&&following.current&&viewport.current)viewport.current.scrollTop=viewport.current.scrollHeight
  },[active,open,thinking.text])
  return <section className={`capstone-thinking-process${active?' is-active':''}${expanded?' is-reader':''}`} role="region" aria-label={kind==='call'?'LLM 思考':thinking.handedOff?'初始思考记录':'思考状态'} data-phase={thinking.phase} aria-busy={active}>
    <button type="button" className="capstone-thinking-trigger" aria-label={`${open?'折叠':'展开'}${kind==='call'?'本轮思考':'初始思考'}`} aria-description={status} aria-expanded={open} aria-controls={open&&thinking.text?bodyId:undefined} onClick={()=>{
      following.current=true;setFold({id:foldId,open:!open});saveProcessStepOpen(storageKey,foldId,!open)
    }}><ChevronRight aria-hidden="true"/><span className="capstone-thinking-label">{active?'Thinking…':'Thinking'}</span>{!active&&elapsed!==undefined&&<span className="capstone-thinking-duration"> · {elapsed.toFixed(1)}s</span>}</button>
    {open&&thinking.text&&<div id={bodyId} ref={viewport} className="capstone-thinking-copy" onScroll={()=>{
      const node=viewport.current
      if(node)following.current=node.scrollHeight-node.scrollTop-node.clientHeight<24
    }}><MarkdownContent>{thinking.text}</MarkdownContent></div>}
  </section>
}
