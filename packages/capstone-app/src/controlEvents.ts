/** Read-only Control facts. Observation sequences are not Thread event sequences. */
export type ControlEventState={revision:number;objective_revision:number;state:string;reason:string|null}
export type ControlTaskEventState={task_id:string;task_revision:number;objective_revision:number;generation:number;state:string;
 delegation_id:string|null;binding:{thread_id:string;work_id:string}|null;requested_control:string|null;
 control_revision:number|null;delivery_revision:number|null}
export type ControlEvent={schema:'capstone-control-event/1';source:'capstone-control';workspace:string;goal_id:string;
 event_id:string;sequence:number;kind:string;recorded_at:string;before:ControlEventState|null;after:ControlEventState;
 task_changes:{task_id:string;before:ControlTaskEventState|null;after:ControlTaskEventState|null}[];
 observation_sequence?:number;observed_state?:string;delegation_id?:string;operation_id?:string;
 history_complete:boolean;missing_goal_revisions:{from:number;through:number}|null}
export type ControlEventPage={schema:'capstone-control-events/1';workspace:string;goal_id:string;events:ControlEvent[];
 after_sequence:number;through_sequence:number;next_sequence:number;has_more:boolean;history_complete:boolean;
 first_recorded_goal_revision:number|null}
function invalid():never{throw new Error('控制事件记录无效，已停止载入。')}
function object(v:unknown):Record<string,unknown>{if(!v||typeof v!=='object'||Array.isArray(v))return invalid();return v as Record<string,unknown>}
function text(v:unknown):string{if(typeof v!=='string'||!v.trim()||v.length>512)return invalid();return v}
function integer(v:unknown,min=0):number{if(typeof v!=='number'||!Number.isSafeInteger(v)||v<min)return invalid();return v}
function boolean(v:unknown):boolean{if(typeof v!=='boolean')return invalid();return v}
const nullableText=(v:unknown)=>v===null?null:text(v)
const nullableInteger=(v:unknown)=>v===null?null:integer(v)
function state(v:unknown):ControlEventState{const s=object(v);return {revision:integer(s.revision,1),
 objective_revision:integer(s.objective_revision,1),state:text(s.state),reason:nullableText(s.reason)}}
function task(v:unknown,id:string):ControlTaskEventState|null{
 if(v===null)return null
 const s=object(v),binding=s.binding===null?null:object(s.binding)
 if(s.task_id!==id)return invalid()
 return {task_id:id,task_revision:integer(s.task_revision,1),objective_revision:integer(s.objective_revision,1),
  generation:integer(s.generation),state:text(s.state),delegation_id:nullableText(s.delegation_id),
  binding:binding?{thread_id:text(binding.thread_id),work_id:text(binding.work_id)}:null,
  requested_control:nullableText(s.requested_control),control_revision:nullableInteger(s.control_revision),
  delivery_revision:nullableInteger(s.delivery_revision)}
}
export function parseControlEvents(value:unknown,workspace:string,goalId:string,after:number,through?:number):ControlEventPage{
 const p=object(value)
 if(p.schema!=='capstone-control-events/1'||p.workspace!==workspace||p.goal_id!==goalId
  ||!Array.isArray(p.events)||p.events.length>100||p.after_sequence!==after)return invalid()
 const high=integer(p.through_sequence),next=integer(p.next_sequence),more=boolean(p.has_more)
 if(high<after||(through!==undefined&&high!==through))return invalid()
 let previous=after
 const ids=new Set<string>()
 const events=p.events.map(v=>{
  const e=object(v),sequence=integer(e.sequence,1),id=text(e.event_id)
  if(e.schema!=='capstone-control-event/1'||e.source!=='capstone-control'||e.workspace!==workspace||e.goal_id!==goalId
   ||sequence!==previous+1||sequence>high||ids.has(id)||!Array.isArray(e.task_changes)||e.task_changes.length>128)return invalid()
  previous=sequence;ids.add(id)
  const recorded=text(e.recorded_at)
  if(!Number.isFinite(Date.parse(recorded)))return invalid()
  const before=e.before===null?null:state(e.before),current=state(e.after)
  if(before&&before.revision>=current.revision)return invalid()
  const tasks=new Set<string>()
  const changes=e.task_changes.map(v=>{
   const c=object(v),id=text(c.task_id)
   if(tasks.has(id))return invalid()
   tasks.add(id)
   const before=task(c.before,id),after=task(c.after,id)
   if(!before&&!after)return invalid()
   return {task_id:id,before,after}
  })
  const gap=e.missing_goal_revisions===null?null:object(e.missing_goal_revisions)
  const missing=gap?{from:integer(gap.from,1),through:integer(gap.through,1)}:null
  if(missing&&missing.from>missing.through)return invalid()
  return {schema:'capstone-control-event/1' as const,source:'capstone-control' as const,workspace,goal_id:goalId,
   event_id:id,sequence,kind:text(e.kind),recorded_at:recorded,before,after:current,task_changes:changes,
   history_complete:boolean(e.history_complete),missing_goal_revisions:missing,
   ...(e.observation_sequence!==undefined?{observation_sequence:integer(e.observation_sequence)}:{}),
   ...(e.observed_state!==undefined?{observed_state:text(e.observed_state)}:{}),
   ...(e.delegation_id!==undefined?{delegation_id:text(e.delegation_id)}:{}),
   ...(e.operation_id!==undefined?{operation_id:text(e.operation_id)}:{})}
 })
 if(next!==previous||more!==(next<high))return invalid()
 return {schema:'capstone-control-events/1',workspace,goal_id:goalId,events,after_sequence:after,through_sequence:high,
  next_sequence:next,has_more:more,history_complete:boolean(p.history_complete),
  first_recorded_goal_revision:p.first_recorded_goal_revision===null?null:integer(p.first_recorded_goal_revision,1)}
}

export const controlEventLabel=(kind:string)=>({
 'goal.created':'目标已创建','command.delegate_next':'调度下一阶段','delegation.bound':'执行会话已绑定',
 'execution.observed':'接收执行观察','delivery.recorded':'交付已记录','command.verify_task':'阶段交付已核验',
 'command.pause':'请求暂停','command.cancel':'请求撤销','command.resume':'请求恢复',
 'command.revise':'修改目标','command.accept':'最终成果已接受','deadline.expired':'执行期限已到',
} as Record<string,string>)[kind]??'其他控制事件'
