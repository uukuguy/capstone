import {useState} from 'react'
import RequestContextBody from './RequestContextBody'
import type {EventEnvelope} from './threadProtocol'

type RecordValue=Record<string,unknown>
const record=(value:unknown):RecordValue=>value&&typeof value==='object'&&!Array.isArray(value)?value as RecordValue:{}
const fields={
  business_report:'任务进展',open_items:'未完成事项',acceptance:'验收状态',handoff:'任务交接',
  execution:'执行状态',unconfirmed_instruction_refs:'待确认指令',workflow:'任务计划',
}
const reportFields={completed:'已完成',open:'待完成',defects:'缺陷',blockers:'阻塞'} as const

export default function TaskContextPanel({events,work,workId,labels,onLocate}:{
  events:readonly EventEnvelope[];work:unknown;workId?:string;labels:Record<string,string>;onLocate:(attempt:string)=>void
}){
  const [selection,setSelection]=useState('')
  const revisions=new Map<string,RecordValue>()
  function add(value:unknown){
    const state=record(record(value).task_state)
    if(state.schema==='capstone-task-state/1'&&record(state.task).work_id===workId&&typeof state.revision_ref==='string')
      revisions.set(state.revision_ref,state)
  }
  for(const event of events)
    if(event.visibility==='public'&&event.payload.work_id===workId)add(event.payload.work)
  add(work)
  const checkpoint=record(record(work).execution_checkpoint)
  const active=typeof checkpoint.attempt_id==='string'?checkpoint.attempt_id:undefined
  const instructionForAttempt=new Map<string,string>()
  for(const [attempt,state] of revisions){
    const turn=record(state.execution).turn_id
    instructionForAttempt.set(attempt,typeof turn==='string'?turn:attempt)
  }
  if(active)instructionForAttempt.set(active,typeof checkpoint.turn_id==='string'?checkpoint.turn_id:active)
  const attemptsByInstruction=new Map<string,string>()
  const instructionLabels=new Map<string,string>()
  for(const [attempt,instruction] of instructionForAttempt){
    attemptsByInstruction.set(instruction,attempt)
    if(labels[attempt])instructionLabels.set(instruction,labels[attempt])
  }
  const instructions=[...attemptsByInstruction.keys()].reverse()
  const instruction=instructions.includes(selection)?selection:instructions[0]
  const id=instruction?attemptsByInstruction.get(instruction):undefined
  const after=id?revisions.get(id):undefined
  let predecessor=after?after.previous_revision_ref:checkpoint.task_state_ref
  const visited=new Set<string>()
  // Several attempts can settle the same instruction. Follow the exact chain
  // back to the state inherited before the first of those attempts.
  while(typeof predecessor==='string'&&instructionForAttempt.get(predecessor)===instruction&&!visited.has(predecessor)){
    visited.add(predecessor)
    predecessor=revisions.get(predecessor)?.previous_revision_ref
  }
  const before=typeof predecessor==='string'&&!visited.has(predecessor)?revisions.get(predecessor):undefined
  const changes=before&&after?Object.entries(fields).filter(([field])=>
    JSON.stringify(before[field])!==JSON.stringify(after[field])):[]
  const report=record(after?.business_report)
  return <section className="context-inspector task-context-panel" aria-label="任务上下文">
    <header className="context-inspector-heading"><div className="context-scope">任务上下文</div>
      {id&&<button type="button" onClick={()=>onLocate(id)}>定位指令</button>}
    </header>
    {!id?<p>当前会话暂无已保存的任务修订。</p>:<>
      <label className="context-instruction-filter"><span>指令</span>
        <select aria-label="按指令查看任务上下文" value={instruction} onChange={event=>setSelection(event.target.value)}>
          {instructions.map((key,index)=><option key={key} value={key}>{instructionLabels.get(key)||`指令 ${instructions.length-index}`}</option>)}
        </select>
      </label>
      <h4>执行前</h4>
      {before?<ContextRevision label="继承的任务修订" value={before}/>:<p>{predecessor?'此会话记录未包含继承修订的正文。':'没有已记录的前序任务修订。'}</p>}
      {id===active&&<><h4>执行中</h4><ContextRevision label="当前执行检查点" value={checkpoint}/></>}
      <h4>执行后</h4>
      {after?<>
        {Object.entries(reportFields).map(([field,label])=>{
          const items=report[field]
          return Array.isArray(items)&&items.length>0?<div key={field}><strong>{label}</strong>
            <ul>{items.filter((item):item is string=>typeof item==='string').map((item,index)=><li key={index}>{item}</li>)}</ul>
          </div>:null
        })}
        <ContextRevision label="本次保存的任务修订" value={after}/>
        {before&&<><h4>本条指令的变化</h4>{changes.length?changes.map(([field,label])=><details className="context-input-group" key={field}>
          <summary>{label} · {before[field]===undefined?'新增':after[field]===undefined?'移除':'变更'}</summary>
          {before[field]!==undefined&&<ContextRevision label="执行前" value={before[field]}/>}
          {after[field]!==undefined&&<ContextRevision label="执行后" value={after[field]}/>}
        </details>):<p>已记录的任务字段没有变化。</p>}</>}
      </>:<p>本条指令尚无已保存的结果修订。</p>}
    </>}
  </section>
}

function ContextRevision({label,value}:{label:string;value:unknown}){
  return <details className="capstone-call-tool context-input-group">
    <summary>{label}</summary>
    <div className="capstone-call-tool-detail context-entry-body"><RequestContextBody text={JSON.stringify(value)}/></div>
  </details>
}
