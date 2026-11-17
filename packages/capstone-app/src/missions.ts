import {ThreadProtocolError} from './threadProtocol'
export type MissionRef={missionId:string;workId?:string}
export type MissionCreate={schema:'capstone-control-mission-create/1';operation_id:string;objective:string;origin:{thread_id:string;work_id?:string}}
export type Mission={missionId:string;objective:string;state:string;revision:number;planComplete:boolean;origin:{thread_id:string;work_id?:string}}
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
  return {missionId:id(row.mission_id),objective:row.objective,state:row.state,revision:row.revision as number,planComplete:row.plan_complete,origin:{thread_id:id(origin.thread_id),...(origin.work_id===undefined?{}:{work_id:id(origin.work_id)})}}
}
