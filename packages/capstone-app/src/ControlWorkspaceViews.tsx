import {useCallback,useEffect,useId,useRef,useState,type ReactNode} from 'react'
import {Columns3,Activity,ScanSearch,ArrowLeft,RefreshCw} from 'lucide-react'
import ControlTaskBoard,{taskIdentity} from './ControlTaskBoard'
import type {ControlGoal} from './controlGoals'
import {controlEventLabel,type ControlEvent,type ControlEventPage,type ControlTaskEventState} from './controlEvents'
import './ControlWorkspaceViews.css'

type Perspective='tasks'|'runtime'|'diagnosis'
type Props={goal:ControlGoal;disabled:boolean;onOpenThread:(thread:string,work:string)=>void;
 onVerify:(task:string,revision:number)=>void;readEvents:(goal:string,after?:number,through?:number)=>Promise<ControlEventPage>;taskControls?:ReactNode}
const states:Record<string,string>={ready:'待执行',running:'执行中',waiting:'等待处理',paused:'已暂停',pausing:'暂停请求待确认',
 cancelling:'撤销请求待确认',cancelled:'已终止',revising:'等待旧执行停止',delivered:'待核验',accepted:'已接受',
 pending:'待开始',dispatching:'派发中',resume_requested:'恢复请求待确认',revoke_requested:'停止请求待确认',
 blocked:'受阻',failed:'执行失败',verified:'已核验',completed:'执行已完成',unknown:'状态待确认'}
const stateLabel=(state:string)=>states[state]??state
const tabs=[{id:'tasks' as const,label:'任务执行',Icon:Columns3},{id:'runtime' as const,label:'运行观察',Icon:Activity},
 {id:'diagnosis' as const,label:'研发诊断',Icon:ScanSearch}]
const LIMIT=500

export default function ControlWorkspaceViews(props:Props){
 return <Workspace key={JSON.stringify([props.goal.workspace,props.goal.goal_id])} {...props}/>
}
function Workspace({goal,disabled,onOpenThread,onVerify,readEvents,taskControls}:Props){
 const id=useId(),[view,setView]=useState<Perspective>('tasks')
 const [page,setPage]=useState<ControlEventPage|null>(null),[events,setEvents]=useState<ControlEvent[]>([])
 const [selected,setSelected]=useState<string|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('')
 const [selectedTask,setSelectedTask]=useState<string|null>(null)
 const epoch=useRef(0),inflight=useRef(false),returnFocus=useRef<HTMLButtonElement|null>(null)
 const detail=useRef<HTMLElement|null>(null)
 useEffect(()=>()=>{epoch.current++;inflight.current=false},[])
 const load=useCallback(async(more=false)=>{
  if(inflight.current)return
  inflight.current=true;const request=++epoch.current
  setBusy(true);setError('')
  try{
   const next=await readEvents(goal.goal_id,more?page?.next_sequence??0:0,more?page?.through_sequence:undefined)
   if(epoch.current!==request)return
   if(next.goal_id!==goal.goal_id||next.workspace!==goal.workspace)throw new Error('事件不属于当前目标。')
   setPage(next);setEvents(old=>more?[...old,...next.events].slice(0,LIMIT):next.events)
  }catch(e){if(epoch.current===request)setError(e instanceof Error?e.message:'控制事件读取失败')}
  finally{if(epoch.current===request){inflight.current=false;setBusy(false)}}
 },[goal.goal_id,goal.workspace,page,readEvents])
 useEffect(()=>{if(view!=='tasks'&&!page&&!busy&&!error)void load()},[view,page,busy,error,load])
 const selectedEvent=events.find(e=>e.event_id===selected)
 const diagnose=(event:ControlEvent,button:HTMLButtonElement)=>{
  setSelected(event.event_id);returnFocus.current=button
  const source=event.task_changes.length===1?event.task_changes[0]:null
  const task=source&&goal.tasks.find(t=>t.task_id===source.task_id&&[source.before,source.after].some(
   s=>s?.task_revision===t.revision&&s.objective_revision===goal.objective_revision))
  if(task)setSelectedTask(taskIdentity(goal,task))
  setView('diagnosis')
 }
 useEffect(()=>{if(view==='diagnosis'&&selected)detail.current?.focus({preventScroll:true})},[view,selected])
 const back=()=>{setView('runtime');requestAnimationFrame(()=>returnFocus.current?.focus({preventScroll:true}))}
 const links=(event:ControlEvent)=>{
  const found=new Map<string,ControlTaskEventState>()
  for(const change of event.task_changes)for(const task of [change.before,change.after]){
   if(task?.binding)found.set(JSON.stringify(task.binding),task)
  }
  return [...found.values()]
 }
 return <div className="control-perspectives">
  <div role="tablist" aria-label="工作空间视角" className="control-perspective-tabs">
   {tabs.map(({id:key,label,Icon})=><button key={key} id={id+'-'+key} role="tab" aria-selected={view===key}
    aria-controls={id+'-panel-'+key} tabIndex={view===key?0:-1} onClick={()=>setView(key)}
    onKeyDown={e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault()
     const next=e.key==='Home'?0:e.key==='End'?2:(tabs.findIndex(t=>t.id===view)+(e.key==='ArrowRight'?1:2))%3
     setView(tabs[next].id);document.getElementById(id+'-'+tabs[next].id)?.focus()}}>
    <Icon size={17} aria-hidden="true"/>{label}</button>)}
  </div>
  <div role="tabpanel" id={id+'-panel-tasks'} aria-labelledby={id+'-tasks'} hidden={view!=='tasks'}>
   {taskControls}
   <ControlTaskBoard goal={goal} disabled={disabled} onOpenThread={onOpenThread} onVerify={onVerify}
    selection={selectedTask} onSelect={setSelectedTask}/>
  </div>
  {view!=='tasks'&&<div className="control-observation-toolbar">
   <div><strong>{view==='runtime'?'控制面与执行任务':'事件轨迹与来源记录'}</strong>
    <p>当前状态与事件读取上界分别显示；Control 观察序号不等于 Agent 轨迹序号。</p></div>
   <button disabled={busy} onClick={()=>void load()}><RefreshCw size={14} aria-hidden="true"/>刷新事件</button>
  </div>}
  {view!=='tasks'&&<div className="control-event-coverage" role="status">
   {busy?'正在读取事件…':page?<>Control 事件上界 #{page.through_sequence} · 已载入 {events.length} 条
    {!page.history_complete&&<span>历史不完整：{page.first_recorded_goal_revision===null?'尚无持久事件；旧轨迹未采集。':`从状态版本 ${page.first_recorded_goal_revision} 开始记录，可能存在缺口。`}</span>}</>:'尚未读取事件'}
   {error&&<p role="alert">{error}。{page?'保留上次成功读取的事件。':'当前状态不能替代缺失的事件。'}</p>}
   {page&&!page.has_more&&events.length>0&&goal.revision>events[events.length-1].after.revision&&<p>当前状态已有更新；本次事件阅读范围保持不变，可刷新事件读取新范围。</p>}
  </div>}
  <div role="tabpanel" id={id+'-panel-runtime'} aria-labelledby={id+'-runtime'} hidden={view!=='runtime'}>
   <div className="control-runtime-summary">
    <span><small>当前控制面</small><strong>{stateLabel(goal.state)}</strong></span>
    <span><small>目标要求版本 / 状态版本</small><strong>{goal.objective_revision} / {goal.revision}</strong></span>
    <span><small>已委托 / 预算</small><strong>{goal.delegations_admitted} / {goal.max_delegations}</strong></span>
   </div>
   <div className="control-runtime-lanes" aria-label="运行泳道" tabIndex={0}>
    <section className="control-runtime-lane"><header><strong>Control 控制面</strong><small>按持久事件序号排列</small></header>
     <div className="control-lane-events">{events.length?events.map(event=><button key={event.event_id}
      aria-label={`诊断控制事件 #${event.sequence}`} aria-pressed={selected===event.event_id}
      className="control-event-node" onClick={e=>diagnose(event,e.currentTarget)}>
      <small>#{event.sequence} · {new Date(event.recorded_at).toLocaleTimeString()}</small>
      <strong>{controlEventLabel(event.kind)}</strong><span>{stateLabel(event.after.state)}</span>
     </button>):<p className="control-lane-empty">尚无可显示的持久事件。下方为当前状态，不代表历史轨迹。</p>}</div>
    </section>
    {goal.tasks.map((task,index)=><section className="control-runtime-lane" key={JSON.stringify([goal.objective_revision,task.task_id,task.revision])}>
     <header><button aria-pressed={selectedTask===taskIdentity(goal,task)} onClick={()=>setSelectedTask(taskIdentity(goal,task))}>阶段 {index+1}</button><small>当前任务版本 {task.revision}</small></header>
     <div className="control-runtime-task"><div><strong>{task.objective}</strong>
      <span className={['failed','blocked','revoke_requested'].includes(task.state)?'control-attention':''}>{stateLabel(task.state)}</span>
      <p>{task.observation?.summary||'尚无执行观察摘要。'}</p>
      {task.delegation&&<p>执行要求版本 {task.delegation.goal_revision??'未提供'} · 第 {task.delegation.generation??'未知'} 次委托</p>}
      {task.delegation?.agent_id&&<small>Agent · {task.delegation.agent_id}</small>}
      {task.observation&&<small>最新 Control 接收观察 #{task.observation.sequence} · 来源状态 {stateLabel(task.observation.state)}</small>}
      </div><div className="control-runtime-links">
       {task.delegation?.binding?<button onClick={()=>onOpenThread(task.delegation!.binding!.thread_id,task.delegation!.binding!.work_id)}>打开当前执行会话</button>:<small>尚未绑定执行会话</small>}
       {events.filter(e=>e.task_changes.some(c=>c.task_id===task.task_id&&[c.before,c.after].some(s=>s?.task_revision===task.revision&&s.objective_revision===(task.delegation?task.delegation.goal_revision:goal.objective_revision)))).slice(-3).map(event=>
        <button key={event.event_id} onClick={e=>diagnose(event,e.currentTarget)}>事件 #{event.sequence} · {controlEventLabel(event.kind)}</button>)}
      </div></div>
    </section>)}
   </div>
   <p className="control-observation-note">泳道展示组织关系，当前调度仍为一个活跃委托。请求停止与停止确认分别记录；此处不重建模型内部推理。</p>
  </div>
  <div role="tabpanel" id={id+'-panel-diagnosis'} aria-labelledby={id+'-diagnosis'} hidden={view!=='diagnosis'}>
   <div className="control-diagnostic-layout">
    <nav aria-label="控制事件轨迹" className="control-event-index">{events.map(event=><button key={event.event_id}
      aria-pressed={selected===event.event_id} onClick={()=>setSelected(event.event_id)}>
      <small>#{event.sequence} · 状态版本 {event.after.revision}</small><strong>{controlEventLabel(event.kind)}</strong>
     </button>)}{!events.length&&<p>没有已采集的事件。</p>}</nav>
    <section aria-label="事件诊断详情" className="control-event-detail" ref={detail} tabIndex={-1}>
     <button onClick={back}><ArrowLeft size={14} aria-hidden="true"/>返回运行观察</button>
     {selectedEvent?<><h4>{controlEventLabel(selectedEvent.kind)}</h4>
      <p>这里展示该事件的记录；不代表当前完整现场，也不执行重放。</p>
      <dl><dt>事件身份</dt><dd>{selectedEvent.event_id}</dd><dt>来源 / 序号</dt><dd>capstone-control / #{selectedEvent.sequence}</dd>
       <dt>记录时间</dt><dd>{new Date(selectedEvent.recorded_at).toLocaleString()}</dd>
       <dt>记录的状态变化</dt><dd>{selectedEvent.before?stateLabel(selectedEvent.before.state):'无前态'} → {stateLabel(selectedEvent.after.state)}</dd>
       <dt>状态版本</dt><dd>{selectedEvent.before?.revision??'无'} → {selectedEvent.after.revision}</dd>
       {selectedEvent.observation_sequence!==undefined&&<><dt>接收的观察序号</dt><dd>{selectedEvent.observation_sequence}（不是 Thread 事件序号）</dd></>}
       {selectedEvent.operation_id&&<><dt>操作身份</dt><dd>{selectedEvent.operation_id}</dd></>}
      </dl>
      {selectedEvent.missing_goal_revisions&&<p className="control-attention">缺少状态版本 {selectedEvent.missing_goal_revisions.from}–{selectedEvent.missing_goal_revisions.through} 的事件。</p>}
      {links(selectedEvent).map(task=><div className="control-record-binding" key={JSON.stringify(task.binding)}>
       <p>记录中的任务 {task.task_id} · 要求版本 {task.objective_revision} · 任务版本 {task.task_revision} · 第 {task.generation} 次委托</p>
       <code>{task.binding!.thread_id} / {task.binding!.work_id}</code>
       <button onClick={()=>onOpenThread(task.binding!.thread_id,task.binding!.work_id)}>打开记录中的执行会话</button>
      </div>)}
      <details><summary>查看已发布的事件记录</summary><pre>{JSON.stringify(selectedEvent,null,2)}</pre></details>
     </>:<p>{selected?'所选事件不在当前已载入的范围，请继续载入或返回原读取边界。':'从运行观察的关键节点，或左侧事件轨迹选择一条记录。'}</p>}
    </section>
   </div>
  </div>
  {view!=='tasks'&&page?.has_more&&<div className="control-event-pagination">{events.length<LIMIT
   ?<button disabled={busy} onClick={()=>void load(true)}>载入更多事件</button>
   :<p>本次阅读已达 {LIMIT} 条上限。完整历史仍保存在服务端；此界面暂不支持跨窗口定位。</p>}</div>}
 </div>
}
