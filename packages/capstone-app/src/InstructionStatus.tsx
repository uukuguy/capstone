import {useState} from 'react'
import {Circle, ListOrdered, Square, ChevronDown} from 'lucide-react'
import type {QueuedInstruction} from './threadWorkProtocol'
import './instructionStatus.css'

export default function InstructionStatus({active,stopping,stopped,waiting,queue,disabled,canStop,onStop,onWithdraw,onLocate}:{active:boolean;stopping:boolean;stopped:boolean;waiting:boolean;queue:QueuedInstruction[];disabled:boolean;canStop:boolean;onStop:()=>void;onWithdraw:(id:string)=>void;onLocate:(attemptId:string)=>void}){
  const [expanded,setExpanded]=useState(false)
  const pending=queue.filter(item=>item.state==='pending')
  const status=stopping?'正在停止':waiting?'待你回复':active?'执行中':stopped?'已停止':''
  return <div className="instruction-status">
    {expanded&&<section className="instruction-queue" aria-label="待接纳指令">
      <p>补充文字沿用当前执行的模型、权限和资料。</p>
      {!pending.length&&<p>没有待接纳指令。</p>}
      {pending.map(item=><article key={item.id}><p>{item.text}</p><span>待接纳</span><button type="button" disabled={disabled||stopping} onClick={()=>onWithdraw(item.id)}>撤回</button><button type="button" onClick={()=>onLocate(item.attemptId)}>查看来源执行</button></article>)}
      {stopped&&pending.length>0&&<p>已停止。待接纳指令保留，继续执行后处理。</p>}
    </section>}
    <div className="instruction-status-strip"><span role="status">{status&&<><Circle aria-hidden="true"/>{status}</>}</span><div>
      <button type="button" aria-expanded={expanded} aria-label={`待接纳指令 ${pending.length}`} title="查看待接纳指令" onClick={()=>setExpanded(value=>!value)}><ListOrdered aria-hidden="true"/><span>{pending.length}</span><ChevronDown aria-hidden="true"/></button>
      {canStop&&<button type="button" aria-label="停止生成" title="停止生成" disabled={disabled||stopping} onClick={onStop}><Square aria-hidden="true"/></button>}
    </div></div>
  </div>
}
