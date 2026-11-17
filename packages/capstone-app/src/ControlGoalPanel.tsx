import {useCallback,useEffect,useRef,useState} from 'react'
import {Target} from 'lucide-react'
import AnswerDetailSheet from './AnswerDetailSheet'
import ControlWorkspaceViews from './ControlWorkspaceViews'
import {commandKey} from './commandKey'
import {buildControlGoal,controlGoalCommand,type ControlCommand,type ControlDraft,type ControlGoal,type ControlGoalCreate} from './controlGoals'
import type {HttpThreadTransport} from './threadHttpTransport'
import './ControlGoalPanel.css'
import {missionStateLabel} from './missions'
import {navigateSession} from './SessionNavigation'

type Transport=Pick<HttpThreadTransport,'workspaceName'|'controlGoals'|'controlGoal'|'createControlGoal'|'controlGoalCommand'|'controlEvents'>
type Pending={kind:'create';body:ControlGoalCreate}|{kind:'command';body:ControlCommand}
const names:Record<string,string>={planning:'规划中',ready:'待执行',running:'推进中',waiting:'等待处理',paused:'已暂停',pausing:'暂停中',
  cancelling:'撤销中',cancelled:'已撤销',revising:'等待旧阶段停止',delivered:'待最终接受',accepted:'已接受',
  pending:'待前置阶段',dispatching:'正在委托',delivered_task:'待阶段核验',verified:'阶段核验通过',
  revoke_requested:'等待停止确认',resume_requested:'正在恢复',blocked:'需处理',failed:'执行失败',completed:'执行已完成'}
const fresh=():ControlDraft=>({objective:'',criteria:'',maxDelegations:8,deadline:new Date(Date.now()+86400000).toISOString(),
  stages:[{objective:'',files:'',mode:'single',maxAttempts:1},{objective:'',files:'',mode:'single',maxAttempts:1}]})
function read<T>(key:string,fallback:T):T{try{return JSON.parse(localStorage.getItem(key)||'null')??fallback}catch{return fallback}}
function write(key:string,value:unknown){try{localStorage.setItem(key,JSON.stringify(value))}catch{/* Live draft remains available. */}}
function reason(value:string){return ({user_pause:'用户已暂停',user_cancel:'用户已撤销',objective_revised:'目标已修改，正在停止旧阶段',
  deadline_exhausted:'执行期限已到',delegation_budget_exhausted:'委托预算已用完',delegation_failed:'阶段执行失败，请查看会话记录',
  delegation_unknown:'阶段结果尚未确认，需要核对后处理',agent_paused:'阶段已暂停，请查看会话状态',agent_waiting:'阶段等待处理'} as Record<string,string>)[value]||'请打开阶段会话查看待处理事项。'}
function draftFromStorage(key:string):ControlDraft{
  const value=read<ControlDraft|null>(key,null)
  if(!value||typeof value.objective!=='string'||typeof value.criteria!=='string'||!Number.isSafeInteger(value.maxDelegations)
    ||!Number.isFinite(Date.parse(value.deadline))||!Array.isArray(value.stages)||!value.stages.length||value.stages.length>64
    ||!value.stages.every(s=>s&&typeof s.objective==='string'&&typeof s.files==='string'&&['single','goal'].includes(s.mode)&&Number.isSafeInteger(s.maxAttempts)))return fresh()
  return value
}
function pendingFromStorage(key:string):Pending|null{
  const value=read<Pending|null>(key,null)
  if(!value||!value.body||typeof value.body.operation_id!=='string')return null
  if(value.kind==='create'&&value.body.schema==='capstone-control-goal-create/1'&&Array.isArray(value.body.tasks))return value
  if(value.kind==='command'&&value.body.schema==='capstone-control-command/1'&&typeof value.body.goal_id==='string'&&Number.isSafeInteger(value.body.expected_revision))return value
  return null
}

export default function ControlGoalPanel({transport,onOpenThread}:{transport:Transport;onOpenThread:(thread:string,work:string)=>void}){
  return <ControlGoalPanelState key={transport.workspaceName} transport={transport} onOpenThread={onOpenThread}/>
}
function ControlGoalPanelState({transport,onOpenThread}:{transport:Transport;onOpenThread:(thread:string,work:string)=>void}){
  const scope=`capstone.control.${transport.workspaceName}`
  const [open,setOpen]=useState(false),[goals,setGoals]=useState<ControlGoal[]>([]),[selected,setSelected]=useState(()=>read(scope+'.selected',''))
  const [goal,setGoal]=useState<ControlGoal|null>(null),[draft,setDraft]=useState<ControlDraft>(()=>draftFromStorage(scope+'.draft'))
  const [form,setForm]=useState<'create'|'revise'|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false)
  const [pending,setPending]=useState<Pending|null>(()=>pendingFromStorage(scope+'.pending')),[cursor,setCursor]=useState<string|null>(null)
  const readEpoch=useRef(0)
  const readEvents=useCallback((id:string,after?:number,through?:number)=>transport.controlEvents(id,after,through),[transport])
  const saveDraft=(value:ControlDraft)=>{setDraft(value);write(scope+'.draft',value)}
  const rememberPending=(value:Pending|null)=>{setPending(value);write(scope+'.pending',value)}
  const choose=(id:string)=>{readEpoch.current++;setGoal(null);setSelected(id);write(scope+'.selected',id);setForm(null)}
  const refresh=useCallback(async(id=selected)=>{
    const epoch=++readEpoch.current
    const page=await transport.controlGoals()
    if(epoch!==readEpoch.current)return
    setGoals(previous=>{
      const next=[...page.goals,...previous.filter(g=>!page.goals.some(item=>item.goal_id===g.goal_id))]
      return next.length===previous.length&&next.every((g,i)=>g.goal_id===previous[i].goal_id&&g.revision===previous[i].revision)?previous:next
    });setCursor(page.nextCursor)
    const target=id||page.goals[0]?.goal_id
    if(target){const next=await transport.controlGoal(target);if(epoch!==readEpoch.current)return;setGoal(previous=>previous?.goal_id===next.goal_id&&previous.revision===next.revision?previous:next);if(!id){setSelected(target);write(scope+'.selected',target)}}
    else setGoal(null)
  },[transport,selected,scope])
  useEffect(()=>{
    if(!open)return
    let active=true
    const load=()=>void refresh().catch(e=>{if(active)setError(e instanceof Error?e.message:'长期目标读取失败')})
    load();const timer=window.setInterval(()=>{
      if(['SELECT','INPUT','TEXTAREA'].includes(document.activeElement?.tagName||''))return
      load()
    },3000)
    return ()=>{active=false;readEpoch.current++;window.clearInterval(timer)}
  },[open,refresh])
  async function perform(operation:Pending){
    if(busy)return
    rememberPending(operation);setBusy(true);setError('')
    try{
      const result=operation.kind==='create'?await transport.createControlGoal(operation.body):await transport.controlGoalCommand(operation.body)
      const current=operation.kind==='create'?result as ControlGoal:(result as {goal:ControlGoal}).goal
      rememberPending(null);choose(current.goal_id);setGoal(current);setForm(null)
      if(operation.kind==='create')saveDraft(fresh())
      await refresh(current.goal_id)
    }catch(e){setError(e instanceof Error?e.message:'请求结果尚未确认，可重试原请求')}
    finally{setBusy(false)}
  }
  function control(kind:string,payload:Record<string,unknown>={}){
    if(goal&&!pending)void perform({kind:'command',body:controlGoalCommand(goal,kind,payload,'control_'+commandKey())})
  }
  function submit(){
    try{
      const body=buildControlGoal(draft,'create_'+commandKey())
      if(form==='revise')control('revise',{objective:body.objective,acceptance_criteria:body.acceptance_criteria,tasks:body.tasks})
      else void perform({kind:'create',body})
    }catch(e){setError(e instanceof Error?e.message:'请检查目标设置')}
  }
  const disabled=busy||!!pending
  const products=goal?.tasks.flatMap(t=>t.delivery?.products||[])||[]
  return <><button type="button" className="thread-control-button" onClick={()=>setOpen(true)}><Target size={16} aria-hidden="true"/>长期目标</button>
    {open&&<AnswerDetailSheet title="长期目标" answerLabel="" showAnswerLabel={false} onClose={()=>setOpen(false)} className="control-goal-sheet">
      <p>组织多个阶段。每个阶段有独立会话；原成果按授权引用接续，最终成果由你接受。</p>
      <div className="control-goal-actions"><button onClick={()=>{setForm('create');setError('')}} disabled={disabled}>新建长期目标</button>
        <button onClick={()=>void refresh().catch(e=>setError(String(e)))} disabled={busy}>刷新状态</button></div>
      {error&&<p role="alert">{error}</p>}
      {pending&&<section aria-label="待确认的目标请求"><p>原请求结果尚未确认。重试会使用同一请求身份和版本。</p>
        <button disabled={busy} onClick={()=>void perform(pending)}>重试原请求</button>
        <button disabled={busy} onClick={()=>rememberPending(null)}>清除本机待确认记录</button><p>清除此记录不会撤销服务端已接收的目标，请先刷新列表核对。</p></section>}
      {goals.length>0&&<label>选择长期目标<select aria-label="选择长期目标" value={selected} onChange={e=>choose(e.target.value)} disabled={disabled}>
        {goals.map(g=><option key={g.goal_id} value={g.goal_id}>{g.objective} · {g.mission?missionStateLabel(g.mission):names[g.state]||g.state} · {g.goal_id.slice(-6)}</option>)}</select></label>}
      {cursor&&<button onClick={()=>void transport.controlGoals(cursor).then(page=>{setGoals(previous=>[...previous,...page.goals]);setCursor(page.nextCursor)}).catch(e=>setError(String(e)))}>更多目标</button>}
      {form?<form onSubmit={e=>{e.preventDefault();submit()}} className="control-goal-form">
        <h3>{form==='revise'?'修改长期目标':'新建长期目标'}</h3>
        <label>长期目标内容<textarea required aria-label="长期目标内容" value={draft.objective} disabled={disabled} onChange={e=>saveDraft({...draft,objective:e.target.value})}/></label>
        <label>最终验收条件<textarea required aria-label="最终验收条件" value={draft.criteria} disabled={disabled} onChange={e=>saveDraft({...draft,criteria:e.target.value})}/></label>
        <div className="control-goal-budget"><label>委托次数上限<input type="number" min="1" max="64" value={draft.maxDelegations} disabled={disabled||form==='revise'} onChange={e=>saveDraft({...draft,maxDelegations:Number(e.target.value)})}/></label>
          <label>执行期限<input type="datetime-local" value={new Date(new Date(draft.deadline).getTime()-new Date(draft.deadline).getTimezoneOffset()*60000).toISOString().slice(0,16)} disabled={disabled||form==='revise'} onChange={e=>{if(e.target.value)saveDraft({...draft,deadline:new Date(e.target.value).toISOString()})}}/></label></div>
        {draft.stages.map((stage,index)=><fieldset key={index} disabled={disabled}><legend>阶段 {index+1}</legend>
          <label>阶段目标<textarea required aria-label={`阶段 ${index+1} 目标`} value={stage.objective} onChange={e=>saveDraft({...draft,stages:draft.stages.map((s,i)=>i===index?{...s,objective:e.target.value}:s)})}/></label>
          <label>成果文件<input aria-label={`阶段 ${index+1} 成果文件`} value={stage.files} placeholder="例如 draft.md，多个文件用逗号分开" onChange={e=>saveDraft({...draft,stages:draft.stages.map((s,i)=>i===index?{...s,files:e.target.value}:s)})}/></label>
          <p>列出的文件保存并核验后接续下一阶段；留空则等待人工阶段核验。</p>
          <label>执行方式<select value={stage.mode} onChange={e=>saveDraft({...draft,stages:draft.stages.map((s,i)=>i===index?{...s,mode:e.target.value as 'single'|'goal',maxAttempts:e.target.value==='single'?1:4}:s)})}><option value="single">单次指令</option><option value="goal">持续目标</option></select></label>
          {stage.mode==='goal'&&<label>执行次数上限<input type="number" min="1" max="32" value={stage.maxAttempts} onChange={e=>saveDraft({...draft,stages:draft.stages.map((s,i)=>i===index?{...s,maxAttempts:Number(e.target.value)}:s)})}/></label>}
          {draft.stages.length>1&&<button type="button" onClick={()=>saveDraft({...draft,stages:draft.stages.filter((_,i)=>i!==index)})}>移除此阶段</button>}
        </fieldset>)}
        <div className="control-goal-actions"><button type="button" disabled={disabled||draft.stages.length>=64} onClick={()=>saveDraft({...draft,stages:[...draft.stages,{objective:'',files:'',mode:'single',maxAttempts:1}]})}>增加阶段</button>
          <button type="submit" disabled={disabled}>{form==='revise'?'保存修改并撤销旧阶段':'创建并开始'}</button><button type="button" onClick={()=>setForm(null)}>返回目标状态</button></div>
      </form>:goal?<section aria-label="长期目标状态">
        <h3>{goal.objective}</h3><p>{goal.mission?missionStateLabel(goal.mission):names[goal.state]||goal.state} · 目标版本 {goal.objective_revision} · 已委托 {goal.delegations_admitted}/{goal.max_delegations} 次</p>
        {goal.reason&&<p>状态原因：{reason(goal.reason)}</p>}
        <p>期限：{new Date(goal.deadline_at).toLocaleString()}</p>
        <ControlWorkspaceViews goal={goal} disabled={disabled} readEvents={readEvents}
          taskControls={<>
<h4>最终验收条件</h4><ul>{goal.acceptance_criteria.map((c,i)=><li key={i}>{c}</li>)}</ul>
        <div className="control-goal-actions">
          {goal.mission&&<button disabled={disabled} onClick={()=>{navigateSession(goal.mission!.origin.thread_id);setOpen(false)}}>返回 Mission 来源会话</button>}
          {['ready','running','waiting'].includes(goal.state)&&<button disabled={disabled} onClick={()=>control('pause')}>暂停目标</button>}
          {['paused','waiting'].includes(goal.state)&&<button disabled={disabled} onClick={()=>control('resume')}>恢复目标</button>}
          {!['accepted','cancelled','cancelling'].includes(goal.state)&&<button disabled={disabled} onClick={()=>control('cancel')}>撤销目标</button>}
          {!goal.mission&&!['accepted','cancelled','cancelling','revising'].includes(goal.state)&&<button disabled={disabled} onClick={()=>{
            saveDraft({objective:goal.objective,criteria:goal.acceptance_criteria.join('\n'),maxDelegations:goal.max_delegations,deadline:goal.deadline_at,
              stages:goal.tasks.map(t=>({objective:t.objective,files:t.required_products.join(', '),mode:t.mode,maxAttempts:t.max_attempts}))});setForm('revise')
          }}>修改目标与阶段</button>}
          {goal.state==='delivered'&&(!goal.mission||goal.mission.planConcluded===true&&goal.mission.allTasksVerified)&&<button disabled={disabled} onClick={()=>control('accept',{products})}>接受当前成果版本</button>}
        </div>
        {goal.acceptance&&<p role="status">已接受此目标版本及所列成果版本。</p>}
          </>}
          onOpenThread={(thread,work)=>{onOpenThread(thread,work);setOpen(false)}}
          onVerify={(taskId,deliveryRevision)=>control('verify_task',{task_id:taskId,delivery_revision:deliveryRevision,checks:[{name:'用户核验阶段交付',passed:true}]})}/>

      </section>:<p>{selected?'正在读取目标状态…':'还没有长期目标。新建后，各阶段会在后台执行。'}</p>}
    </AnswerDetailSheet>}
  </>
}
