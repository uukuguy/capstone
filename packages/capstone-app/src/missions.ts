import {ThreadProtocolError} from './threadProtocol'
export type MissionRef={missionId:string;workId?:string}
export type MissionCreate={schema:'capstone-control-mission-create/1';operation_id:string;objective:string;origin:{thread_id:string;work_id?:string}}
export type Mission={missionId:string;objective:string;state:string;revision:number;planComplete:boolean;planConcluded?:boolean;allTasksVerified?:boolean;organizerState?:string;origin:{thread_id:string;work_id?:string}}
const object=(value:unknown):Record<string,unknown>=>{if(!value||typeof value!=='object'||Array.isArray(value))throw new ThreadProtocolError('Mission 记录无效');return value as Record<string,unknown>}
const id=(value:unknown):string=>{if(typeof value!=='string'||!/^[a-z][a-z0-9_-]{0,127}$/.test(value))throw new ThreadProtocolError('Mission 身份无效');return value}
export function missionObjectiveFromInput(text:string):string|null{const match=/^\/mission(?:\s+([\s\S]*))?$/.exec(text);return match?(match[1]||'').trim():null}
export function parseMissionRefs(value:unknown):MissionRef[]{
  if(value===undefined)return []
  if(!Array.isArray(value))throw new ThreadProtocolError('Mission 关联无效')
  const refs=value.map(raw=>{const row=object(raw);return {missionId:id(row.mission_id),...(row.work_id===undefined?{}:{workId:id(row.work_id)})}})
  if(new Set(refs.map(ref=>ref.missionId)).size!==refs.length)throw new ThreadProtocolError('Mission 关联重复')
  return refs
}
export function parseMission(value:unknown,workspace:string,threadId:string):Mission{
  const row=object(value),origin=object(row.origin)
  if(row.schema!=='capstone-control-mission/1'||row.workspace!==workspace||row.mission_id!==row.goal_id||origin.thread_id!==threadId||typeof row.objective!=='string'||!row.objective.trim()||typeof row.state!=='string'||!Number.isSafeInteger(row.revision)||(row.revision as number)<1||typeof row.plan_complete!=='boolean')throw new ThreadProtocolError('Mission 来源或状态无效')
  if(row.plan_concluded!==undefined&&typeof row.plan_concluded!=='boolean')throw new ThreadProtocolError('Mission 计划结论无效')
  const organizer=row.organizer===undefined?undefined:object(row.organizer)
  if(organizer&&typeof organizer.state!=='string')throw new ThreadProtocolError('Mission 复盘状态无效')
  return {missionId:id(row.mission_id),objective:row.objective,state:row.state,revision:row.revision as number,planComplete:row.plan_complete,...(row.plan_concluded===undefined?{}:{planConcluded:row.plan_concluded}),...(organizer?{organizerState:organizer.state as string}:{}),allTasksVerified:Array.isArray(row.tasks)&&row.tasks.length>0&&row.tasks.every(task=>object(task).state==='verified'),origin:{thread_id:id(origin.thread_id),...(origin.work_id===undefined?{}:{work_id:id(origin.work_id)})}}
}
const missionLabels:Record<string,string>={planning:'规划中',waiting_review:'等待任务结果复盘',ready:'待执行',running:'执行中',waiting:'待你回复',paused:'已暂停',pausing:'正在暂停',accepted:'已接受',cancelled:'已撤销',cancelling:'正在撤销',failed:'需处理',blocked:'需处理',revising:'正在调整'}
export function missionStateLabel(mission:Mission):string{
  if(mission.state==='waiting_review')return ({running:'正在复盘',reserved:'正在安排复盘',waiting:'待你回复',no_progress:'复盘待调整',blocked:'复盘需处理',failed:'复盘需处理',cancelled:'复盘已停止',interrupted:'复盘已停止'} as Record<string,string>)[mission.organizerState||'']||'等待任务结果复盘'
  if(mission.state==='delivered')return mission.planConcluded===false?'等待任务结果复盘':mission.planConcluded===true&&mission.allTasksVerified?'待验收':'待核对交付状态'
  return missionLabels[mission.state]||'状态待确认'
}
