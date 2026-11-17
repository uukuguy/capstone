import {parseNativeArtifact,type NativeArtifact} from './nativeArtifacts'
import {parseMission,type Mission} from './missions'

export type ControlDraft={objective:string;criteria:string;maxDelegations:number;deadline:string;
  stages:{objective:string;files:string;mode:'single'|'goal';maxAttempts:number}[]}
export type ControlTask={task_id:string;revision:number;objective:string;state:string;mode:'single'|'goal';max_attempts:number;
  delivery_requirements:string[];required_products:string[];depends_on:string[];
  delegation:{delegation_id:string;binding:{thread_id:string;work_id:string}|null;goal_revision?:number;generation?:number;agent_id?:string}|null;
  observation?:{sequence:number;state:string;summary:string};
  delivery:{revision:number;answer_ref:string;products:NativeArtifact[]}|null;verification:Record<string,unknown>|null}
export type ControlGoal={schema:'capstone-control-goal/1';workspace:string;goal_id:string;revision:number;objective_revision:number;
  mission?:Mission
  objective:string;acceptance_criteria:string[];max_delegations:number;delegations_admitted:number;deadline_at:string;
  state:string;reason:string|null;acceptance:Record<string,unknown>|null;tasks:ControlTask[]}
export type ControlCommand={schema:'capstone-control-command/1';operation_id:string;goal_id:string;expected_revision:number;kind:string;payload:Record<string,unknown>}
export type ControlGoalCreate=ReturnType<typeof buildControlGoal>
const states=new Set(['ready','running','waiting','paused','pausing','cancelling','cancelled','revising','delivered','accepted'])
const taskStates=new Set(['pending','dispatching','running','waiting','paused','resume_requested','revoke_requested','cancelled','blocked','failed','delivered','verified'])
function object(value:unknown):Record<string,unknown>{if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('长期目标信息无效');return value as Record<string,unknown>}
function text(value:unknown,limit=16384):string{if(typeof value!=='string'||!value.trim()||value.length>limit)throw new Error('长期目标文本无效');return value}
function integer(value:unknown,minimum=1):number{if(typeof value!=='number'||!Number.isSafeInteger(value)||value<minimum)throw new Error('长期目标版本或预算无效');return value}
function strings(value:unknown):string[]{if(!Array.isArray(value)||value.length>64)throw new Error('长期目标列表无效');return value.map(item=>text(item))}
export function parseControlGoal(value:unknown):ControlGoal{
  const g=object(value)
  const mission=g.application_kind==='mission'?parseMission({...g,schema:'capstone-control-mission/1'},text(g.workspace,128),text(object(g.origin).thread_id,128)):undefined
  if(g.schema!=='capstone-control-goal/1'||(!states.has(String(g.state))&&!(mission&&['planning','waiting_review'].includes(String(g.state)))))throw new Error('长期目标协议无效')
  if(!Array.isArray(g.tasks)||(!g.tasks.length&&!(mission&&['planning','paused','cancelled'].includes(String(g.state))))||g.tasks.length>64)throw new Error('长期目标阶段无效')
  const tasks=g.tasks.map(value=>{
    const t=object(value),d=t.delegation===null?null:object(t.delegation)
    const binding=d?.binding===null||!d?null:object(d.binding)
    const bound=binding?{thread_id:text(binding.thread_id,128),work_id:text(binding.work_id,128)}:null
    const delivery=t.delivery===null?null:object(t.delivery)
    if(!taskStates.has(String(t.state))||!['single','goal'].includes(String(t.mode)))throw new Error('长期目标阶段状态无效')
    let products:NativeArtifact[]=[]
    if(delivery){
      if(!bound||!Array.isArray(delivery.products)||delivery.products.length>256)throw new Error('阶段成果无效')
      products=delivery.products.map(p=>{
        const source=object(p),artifact=parseNativeArtifact(p,bound.thread_id,text(source.attempt_id,128))
        if(artifact.work_id!==bound.work_id)throw new Error('阶段成果不属于此委托')
        return artifact
      })
    }
    const observation=t.observation===undefined?undefined:object(t.observation)
    return {task_id:text(t.task_id,128),revision:integer(t.revision),objective:text(t.objective),state:String(t.state),
      mode:t.mode as 'single'|'goal',max_attempts:integer(t.max_attempts),delivery_requirements:strings(t.delivery_requirements),
      required_products:strings(t.required_products??[]),depends_on:strings(t.depends_on),
      delegation:d?{delegation_id:text(d.delegation_id,128),binding:bound,
        ...(d.goal_revision!==undefined?{goal_revision:integer(d.goal_revision)}:{}),
        ...(d.generation!==undefined?{generation:integer(d.generation)}:{}),
        ...(d.agent_id!==undefined?{agent_id:text(d.agent_id,128)}:{})}:null,
      delivery:delivery?{revision:integer(delivery.revision),answer_ref:text(delivery.answer_ref,128),products}:null,
      verification:t.verification===null?null:object(t.verification),
      ...(observation?{observation:{sequence:integer(observation.sequence,0),state:text(observation.state,128),summary:typeof observation.summary==='string'?observation.summary.slice(0,4096):''}}:{})}
  })
  if(!Number.isFinite(Date.parse(String(g.deadline_at))))throw new Error('长期目标期限无效')
  return {...(mission?{mission}:{}),schema:'capstone-control-goal/1',workspace:text(g.workspace,128),goal_id:text(g.goal_id,128),revision:integer(g.revision),
    objective_revision:integer(g.objective_revision),objective:text(g.objective),acceptance_criteria:strings(g.acceptance_criteria),
    max_delegations:integer(g.max_delegations),delegations_admitted:integer(g.delegations_admitted,0),deadline_at:String(g.deadline_at),
    state:String(g.state),reason:g.reason===null?null:text(g.reason,512),acceptance:g.acceptance===null?null:object(g.acceptance),tasks}
}
export function parseControlGoals(value:unknown){
  const page=object(value)
  if(page.schema!=='capstone-control-goals/1'||!Array.isArray(page.goals)||page.goals.length>64)throw new Error('长期目标列表无效')
  return {goals:page.goals.map(parseControlGoal),nextCursor:page.next_cursor===null?null:text(page.next_cursor,128)}
}
export function controlGoalCommand(goal:ControlGoal,kind:string,payload:Record<string,unknown>,operation:string):ControlCommand{
  return {schema:'capstone-control-command/1',operation_id:operation,goal_id:goal.goal_id,expected_revision:goal.revision,kind,payload}
}
export function buildControlGoal(draft:ControlDraft,operation:string){
  text(draft.objective);text(draft.criteria);integer(draft.maxDelegations)
  if(!Number.isFinite(Date.parse(draft.deadline))||!draft.stages.length||draft.stages.length>64)throw new Error('请设置阶段和有限期限。')
  const tasks=draft.stages.map((stage,index)=>{
    text(stage.objective);integer(stage.maxAttempts)
    const files=stage.files.split(/[,，\n]/).map(x=>x.trim()).filter(Boolean)
    if(files.some(x=>x==='.'||x==='..'||/[\/\\\x00-\x1f\x7f]/.test(x))||new Set(files).size!==files.length)throw new Error('成果请填写不含路径的独立文件名。')
    return {task_id:`stage_${index+1}`,objective:stage.objective,delivery_requirements:files.length?files.map(name=>`保存 ${name}`):['保存回答，等待阶段核验'],
      required_products:files,depends_on:index?[`stage_${index}`]:[],agent_id:'capstone',mode:stage.mode,
      max_attempts:stage.mode==='single'?1:stage.maxAttempts}
  })
  return {schema:'capstone-control-goal-create/1' as const,operation_id:operation,objective:draft.objective,
    acceptance_criteria:draft.criteria.split('\n').map(x=>x.trim()).filter(Boolean),max_delegations:draft.maxDelegations,
    deadline_at:new Date(draft.deadline).toISOString(),tasks}
}
