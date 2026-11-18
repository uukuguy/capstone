import {Circle, Square} from 'lucide-react'
import type {QueuedInstruction} from './threadWorkProtocol'
import './instructionStatus.css'

export default function InstructionStatus({active,stopping,stopped,waiting,queue,disabled,canStop,onStop,onWithdraw,interruptOnSend=false,onInterruptChange}:{active:boolean;stopping:boolean;stopped:boolean;waiting:boolean;queue:QueuedInstruction[];disabled:boolean;canStop:boolean;onStop:()=>void;onWithdraw:(id:string)=>void;interruptOnSend?:boolean;onInterruptChange?:(value:boolean)=>void}){
  const pending=queue.filter(item=>item.state==='pending'||item.state==='delivering')
  const status=stopping?'正在停止':waiting?'待你回复':active?'执行中':stopped?'已停止':''
  if(!pending.length&&!status&&!canStop)return null
  return <div className="instruction-status">
    {pending.length>0&&<ul className="instruction-queue" aria-label="待处理补充指令">
      {pending.map(item=><li key={item.id}><span className="instruction-queue-text">{item.text}</span>
        {item.mode==='interrupt'&&<small>中止并执行</small>}
        {item.state==='pending'?<button type="button" disabled={disabled||stopping} onClick={()=>onWithdraw(item.id)}>撤回</button>:
          <small>送达中</small>}
      </li>)}
    </ul>}
    {(status||canStop)&&<div className="instruction-status-strip">
      {status&&<span role="status"><Circle aria-hidden="true"/>{status}</span>}
      <div className="instruction-status-actions">
        {active&&onInterruptChange&&<select aria-label="执行中发送方式" value={interruptOnSend?'interrupt':'ask'}
          disabled={disabled||stopping} onChange={event=>onInterruptChange(event.target.value==='interrupt')}>
          <option value="ask">插问</option>
          <option value="interrupt">中止并执行</option>
        </select>}
        {canStop&&<button type="button" aria-label="停止生成" title="停止生成" disabled={disabled||stopping} onClick={onStop}><Square aria-hidden="true"/></button>}
      </div>
    </div>}
  </div>
}
