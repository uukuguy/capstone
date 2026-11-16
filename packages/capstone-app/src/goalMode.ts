import {ThreadProtocolError} from './threadProtocol'

export type GoalMode={schema:'capstone-work-goal/1';objective:string;objective_revision:number;
  generation:number;state:string;reason:string|null;max_attempts:number;attempts_admitted:number;
  deadline_at:string;last_settled_attempt_id:string|null}
export type GoalControl='start_goal'|'pause_goal'|'resume_goal'|'cancel_goal'|'revise_goal_objective'
export function parseGoalMode(value:unknown):GoalMode{
  if(!value||typeof value!=='object'||Array.isArray(value))throw new ThreadProtocolError('目标状态无效')
  const g=value as GoalMode
  if(g.schema!=='capstone-work-goal/1'||typeof g.objective!=='string'||!g.objective.trim()
    ||![g.objective_revision,g.generation,g.max_attempts].every(n=>Number.isSafeInteger(n)&&n>0)
    ||!Number.isSafeInteger(g.attempts_admitted)||g.attempts_admitted<0||g.attempts_admitted>g.max_attempts
    ||!['ready','running','waiting','paused','completed','failed','cancelled'].includes(g.state)
    ||typeof g.deadline_at!=='string'||!Number.isFinite(Date.parse(g.deadline_at))
    ||!(g.reason===null||typeof g.reason==='string'))throw new ThreadProtocolError('目标状态无效')
  return {...g}
}
export function goalCommand(threadId:string,runId:string,commandId:string,key:string,workId:string,
  expectedRevision:number,kind:GoalControl,payload:Record<string,string|number>){
  return {schema:'capstone-command/2' as const,thread_id:threadId,run_id:runId,
    command_id:commandId,idempotency_key:key,kind,
    target:{kind:'work' as const,id:workId,expected_revision:expectedRevision},payload}
}
