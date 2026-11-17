import {useState} from 'react'
import type {ControlGoal,ControlTask} from './controlGoals'
import './ControlTaskBoard.css'

type Column='pending'|'active'|'review'|'done'|'closed'|'unknown'
const columns:{id:Column;title:string}[]=[{id:'pending',title:'待开始'},{id:'active',title:'执行中'},
  {id:'review',title:'待核验'},{id:'done',title:'已完成'},{id:'closed',title:'已终止'},{id:'unknown',title:'状态待识别'}]
const stateColumns:Record<string,Column>={pending:'pending',dispatching:'active',running:'active',waiting:'active',paused:'active',
  resume_requested:'active',revoke_requested:'active',blocked:'active',failed:'active',delivered:'review',verified:'done',cancelled:'closed'}
const labels:Record<string,string>={pending:'待开始',dispatching:'派发中',running:'执行中',waiting:'等待处理',paused:'已暂停',
  resume_requested:'继续请求待确认',revoke_requested:'停止请求待确认',blocked:'受阻',failed:'执行失败',
  delivered:'等待核验',verified:'已核验',cancelled:'已终止'}
export function taskColumn(state:string):Column{return stateColumns[state]??'unknown'}
export function taskIdentity(goal:ControlGoal,task:ControlTask){return JSON.stringify([goal.workspace,goal.goal_id,goal.objective_revision,task.task_id,task.revision])}

export default function ControlTaskBoard({goal,disabled,onOpenThread,onVerify,selection:controlledSelection,onSelect}:{
  goal:ControlGoal;disabled:boolean;onOpenThread:(thread:string,work:string)=>void;onVerify:(taskId:string,deliveryRevision:number)=>void;
  selection?:string|null;onSelect?:(identity:string)=>void
}){
 const [localSelection,setLocalSelection]=useState<string|null>(null)
 const selection=controlledSelection===undefined?localSelection:controlledSelection
 const setSelection=(identity:string)=>{setLocalSelection(identity);onSelect?.(identity)}
 const selected=goal.tasks.find(t=>taskIdentity(goal,t)===selection)
   ??goal.tasks.find(t=>['active','review'].includes(taskColumn(t.state)))??goal.tasks[0]
 const index=goal.tasks.indexOf(selected),binding=selected?.delegation?.binding
 const waiting=(task:ControlTask)=>task.depends_on.filter(id=>goal.tasks.find(t=>t.task_id===id)?.state!=='verified')
 const dependency=(task:ControlTask)=>waiting(task).map(id=>goal.tasks.find(t=>t.task_id===id)?.objective??id).join('、')
 const pendingReview=goal.tasks.filter(t=>t.state==='delivered').length
 return <div className="control-task-workspace">
  <div className="control-task-notice" role="status">{pendingReview
   ?`需要核验：${pendingReview} 项阶段交付。核验通过后才能解除后续依赖。`
   :goal.state==='revising'?'目标要求已修改；下方仍为待停止的旧执行，新任务尚未启用。'
   :'任务状态来自执行记录；阶段完成与最终接受分别记录。'}</div>
  <div className="control-task-layout">
   <div className="control-task-board" aria-label="任务看板">
    {columns.filter(c=>!['closed','unknown'].includes(c.id)||goal.tasks.some(t=>taskColumn(t.state)===c.id)).map(column=>{
     const tasks=goal.tasks.filter(t=>taskColumn(t.state)===column.id)
     return <section key={column.id} className={`control-task-column control-task-column-${column.id}`} aria-label={column.title}>
      <h4>{column.title}<span>{tasks.length}</span></h4>
      {tasks.length===0&&<p className="control-task-empty">暂无任务</p>}
      {tasks.map(task=><button key={taskIdentity(goal,task)} type="button" className="control-task-card"
        aria-label={`查看任务：${task.objective}`} aria-pressed={selected===task} onClick={()=>setSelection(taskIdentity(goal,task))}>
       <span className="control-task-number">阶段 {goal.tasks.indexOf(task)+1}</span>
       <strong>{task.objective}</strong>
       <span className={`control-task-status ${['failed','blocked','revoke_requested'].includes(task.state)?'needs-attention':''}`}>{labels[task.state]??'状态待识别'}</span>
       {waiting(task).length>0&&<span className="control-task-dependency">等待：{dependency(task)}</span>}
       <span className="control-task-product">{task.required_products.length?task.required_products.join('、'):'交付要求见详情'}</span>
      </button>)}
     </section>
    })}
   </div>
   {selected&&<aside className="control-task-inspector" aria-label="任务详情">
    <small>阶段 {index+1} · 任务版本 {selected.revision}</small><h4>{selected.objective}</h4>
    <p>{labels[selected.state]??'当前协议无法识别此状态'}</p>
    {selected.observation?.summary&&<p className="control-task-progress">{selected.observation.summary}</p>}
    <h5>交付要求</h5><ul>{selected.delivery_requirements.map((item,i)=><li key={i}>{item}</li>)}</ul>
    {selected.depends_on.length>0&&<><h5>前置任务</h5><ul>{selected.depends_on.map(id=>{
      const task=goal.tasks.find(t=>t.task_id===id)
      return <li key={id}>{task?<button type="button" className="control-task-link" onClick={()=>setSelection(taskIdentity(goal,task))}>{task.objective}</button>:id} · {task?.state==='verified'?'已核验':'尚未满足'}</li>
    })}</ul></>}
    {selected.delivery&&<><h5>阶段交付 · 版本 {selected.delivery.revision}</h5>
     {selected.delivery.products.length?<ul>{selected.delivery.products.map(file=><li key={file.artifact_id}>{file.file_name} · {file.size_bytes} 字节</li>)}</ul>:<p>已保存回答，尚无文件交付。</p>}</>}
    <div className="control-task-detail-actions">
     {binding&&<button type="button" onClick={()=>onOpenThread(binding.thread_id,binding.work_id)}>打开阶段 {index+1} 会话</button>}
     {selected.state==='delivered'&&selected.delivery&&<button type="button" disabled={disabled} onClick={()=>onVerify(selected.task_id,selected.delivery!.revision)}>确认阶段交付</button>}
    </div>
    <p className="control-task-hint">{binding?'在原会话查看完整执行记录和成果。':'此任务尚未绑定执行会话。'}看板不通过拖动改写执行状态。</p>
   </aside>}
  </div>
 </div>
}
