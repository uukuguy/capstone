import {ThreadProtocolError} from './threadProtocol'
import {parseNativeArtifact,type NativeArtifact} from './nativeArtifacts'
export type MissionRef={missionId:string;workId?:string}
export type MissionCreate={schema:'capstone-control-mission-create/1';operation_id:string;objective:string;origin:{thread_id:string;work_id?:string}}
export type MissionOpenItem={kind:string;objective?:string;state?:string;taskId?:string;reason?:string}
export type MissionTask={id:string;objective:string;state:string;execution: "direct"|"single"|"goal"|"origin-goal";dependencies:string[];revision:number}
type MissionCriterion={label:string;status?:'met'|'not_met'|'unknown';explanation?:string;products?:NativeArtifact[]}
export type Mission={tasks?:MissionTask[];openItems?:MissionOpenItem[];criteria?:MissionCriterion[];missionId:string;objective:string;state:string;revision:number;planRevision?:number;planComplete:boolean;planConcluded?:boolean;allTasksVerified?:boolean;organizerState?:string;reason?:string;conclusionStatus?:string;conclusionSummary?:string;origin:{thread_id:string;work_id?:string}}
const object=(value:unknown):Record<string,unknown>=>{if(!value||typeof value!=='object'||Array.isArray(value))throw new ThreadProtocolError('Mission 记录无效');return value as Record<string,unknown>}
const id=(value:unknown):string=>{if(typeof value!=='string'||!/^[a-z][a-z0-9_-]{0,127}$/.test(value))throw new ThreadProtocolError('Mission 身份无效');return value}

function verifiedProducts(evidence:unknown,tasks:unknown):NativeArtifact[]{
  if(!Array.isArray(evidence)||!Array.isArray(tasks))return []
  const products=new Map<string,NativeArtifact>()
  for(const raw of evidence.slice(0,64)){
    try{
      const ref=object(raw)
      if(ref.kind!=='product')continue
      const task=tasks.map(object).find(item=>item.task_id===ref.task_id)
      if(task?.state!=='verified')continue
      const delivery=object(task.delivery)
      if(object(task.verification).delivery_revision!==delivery.revision||!Array.isArray(delivery.products))continue
      const source=delivery.products.map(object).find(item=>item.artifact_id===ref.artifact_id&&item.sha256===ref.sha256)
      if(!source)continue
      const bound=object(object(task.delegation).binding)
      const file=parseNativeArtifact(source,id(bound.thread_id),id(source.attempt_id))
      if(file.work_id===bound.work_id)products.set(file.artifact_id,file)
    }catch{continue}
  }
  return [...products.values()]
}
export function missionObjectiveFromInput(text:string):string|null{const match=/^\/mission(?:\s+([\s\S]*))?$/.exec(text);return match?(match[1]||'').trim():null}
export function parseMissionRefs(value:unknown):MissionRef[]{
  if(value===undefined)return []
  if(!Array.isArray(value))throw new ThreadProtocolError('Mission 关联无效')
  const refs=value.map(raw=>{const row=object(raw);return {missionId:id(row.mission_id),...(row.work_id===undefined?{}:{workId:id(row.work_id)})}})
  if(new Set(refs.map(ref=>ref.missionId)).size!==refs.length)throw new ThreadProtocolError('Mission 关联重复')
  return refs
}

/** Older hosts may assert an opaque conclusion. It cannot unlock final acceptance. */
function typedConclusionSatisfied(row:Record<string,unknown>):boolean{
  try{
    const conclusion=object(row.plan_conclusion),criteria=row.acceptance_criteria,verdicts=conclusion.criteria_verdicts
    if(!Array.isArray(criteria)||!criteria.length||!Array.isArray(verdicts)||verdicts.length!==criteria.length||conclusion.plan_revision!==row.plan_revision||!Array.isArray(row.tasks)||!row.tasks.length||!row.tasks.every(task=>object(task).state==='verified'))return false
    const indices=new Set<number>()
    for(const raw of verdicts){
      const verdict=object(raw),index=verdict.criterion_index,refs=verdict.evidence
      if(typeof index!=='number'||!Number.isSafeInteger(index)||index<0||index>=criteria.length||indices.has(index)||verdict.status!=='met'||typeof verdict.explanation!=='string'||!verdict.explanation.trim()||!Array.isArray(refs)||!refs.length)return false
      indices.add(index)
      for(const rawRef of refs){
        const ref=object(rawRef),task=row.tasks.map(object).find(task=>task.task_id===ref.task_id)
        if(!task||task.state!=='verified')return false
        const delivery=object(task.delivery),verification=object(task.verification)
        if(verification.delivery_revision!==delivery.revision)return false
        if(ref.kind==='product'){
          if(typeof ref.sha256!=='string'||!/^[a-f0-9]{64}$/.test(ref.sha256)||!Array.isArray(delivery.products)||!delivery.products.map(object).some(product=>product.artifact_id===ref.artifact_id&&product.sha256===ref.sha256))return false
        }else if(ref.kind!=='answer'||typeof ref.answer_ref!=='string'||ref.answer_ref!==delivery.answer_ref)return false
      }
    }
    return true
  }catch{return false}
}
export function parseMission(value:unknown,workspace:string,threadId:string):Mission{
  const row=object(value),origin=object(row.origin)
  if(row.schema!=='capstone-control-mission/1'||row.workspace!==workspace||row.mission_id!==row.goal_id||origin.thread_id!==threadId||typeof row.objective!=='string'||!row.objective.trim()||typeof row.state!=='string'||!Number.isSafeInteger(row.revision)||(row.revision as number)<1||typeof row.plan_complete!=='boolean')throw new ThreadProtocolError('Mission 来源或状态无效')
  if(row.plan_concluded!==undefined&&typeof row.plan_concluded!=='boolean')throw new ThreadProtocolError('Mission 计划结论无效')
  const organizer=row.organizer===undefined?undefined:object(row.organizer)
  if(organizer&&typeof organizer.state!=='string')throw new ThreadProtocolError('Mission 复盘状态无效')
  const state = row.task_state === undefined ? undefined : object(row.task_state)
  if (state && (state.schema !== 'capstone-task-state/1' || object(state.task).mission_id !== row.mission_id ||
      state.revision_ref !== String(row.revision) || !Array.isArray(state.open_items)))
    throw new ThreadProtocolError('Mission 任务状态与版本不符')
  const openItems = (state?.open_items as unknown[] | undefined)?.map(value => {
    const item = object(value)
    if (typeof item.kind !== 'string') throw new ThreadProtocolError('Mission 未完成事项无效')
    return {kind:item.kind,objective:typeof item.objective === 'string' ? item.objective : undefined,
      state:typeof item.state === 'string' ? item.state : undefined,
      taskId:typeof item.task_id === 'string' ? id(item.task_id) : undefined,
      reason:typeof item.reason === 'string' ? item.reason : undefined}
  })
  const tasks: MissionTask[] = Array.isArray(row.tasks) ? row.tasks.slice(0,64).flatMap(raw=>{
    const task=object(raw)
    if(typeof task.task_id!=='string'||typeof task.objective!=='string'||typeof task.state!=='string'
      ||(task.mode!=='single'&&task.mode!=='goal'))return []
    const execution=typeof task.origin_attempt_id==='string'?'direct':task.placement==='origin'?'origin-goal':task.mode
    const dependencies=Array.isArray(task.depends_on)?task.depends_on.slice(0,64).map(id):[]
    const revision=typeof task.revision==='number'&&Number.isSafeInteger(task.revision)&&task.revision>0?task.revision:1
    return [{id:id(task.task_id),objective:task.objective,state:task.state,execution,dependencies,revision}]
  }) : []
  const satisfied=typedConclusionSatisfied(row)
  const conclusion=row.plan_conclusion?object(row.plan_conclusion):undefined
  const verdicts=conclusion?.plan_revision===row.plan_revision&&Array.isArray(conclusion?.criteria_verdicts)
    ? new Map(conclusion.criteria_verdicts.slice(0,64).map(value=>{const verdict=object(value);return [verdict.criterion_index,verdict]}))
    : undefined
  const criteria:MissionCriterion[]=Array.isArray(row.acceptance_criteria)?row.acceptance_criteria.slice(0,64).flatMap((label,index)=>{
    if(typeof label!=='string')return []
    const verdict=verdicts?.get(index)
    const status=verdict?.status
    return [{label,...(status==='met'||status==='not_met'||status==='unknown'
      ? {status,explanation:typeof verdict?.explanation==='string'?verdict.explanation:undefined,
        ...(Array.isArray(verdict?.evidence)?{products:verifiedProducts(verdict.evidence,row.tasks)}:{})} : {})}]
  }):[]
  const conclusionStatus=conclusion?(!Array.isArray(conclusion.criteria_verdicts)?'legacy_unverified':conclusion.plan_revision!==row.plan_revision?'stale':satisfied?'satisfied':'incomplete'):row.plan_concluded===true?'legacy_unverified':undefined
  const conclusionSummary=verdicts&&typeof conclusion?.summary==='string'?conclusion.summary:undefined
  return {openItems,tasks,criteria,missionId:id(row.mission_id),objective:row.objective,state:row.state,revision:row.revision as number,
    ...(typeof row.plan_revision==='number'&&Number.isSafeInteger(row.plan_revision)&&row.plan_revision>0?{planRevision:row.plan_revision}:{}),
    planComplete:row.plan_complete,planConcluded:row.plan_concluded===true&&satisfied,...(typeof row.reason==='string'?{reason:row.reason}:{}),conclusionStatus,conclusionSummary,...(organizer?{organizerState:organizer.state as string}:{}),allTasksVerified:Array.isArray(row.tasks)&&row.tasks.length>0&&row.tasks.every(task=>object(task).state==='verified'),origin:{thread_id:id(origin.thread_id),...(origin.work_id===undefined?{}:{work_id:id(origin.work_id)})}}
}
const missionLabels:Record<string,string>={planning:'规划中',waiting_review:'等待任务结果复盘',ready:'待执行',running:'执行中',waiting:'待你回复',paused:'已暂停',pausing:'正在暂停',accepted:'已接受',cancelled:'已撤销',cancelling:'正在撤销',failed:'需处理',blocked:'需处理',revising:'正在调整'}
export function missionStateLabel(mission:Mission):string{
  if(mission.reason==='partial_delivery')return '部分交付'
  if(mission.reason==='acceptance_incomplete'||(mission.state==='delivered'&&mission.conclusionStatus==='incomplete'))return '仍有未完成事项'
  if(mission.conclusionStatus==='legacy_unverified')return '原计划结论待核验'
  if(mission.state==='waiting_review')return ({running:'正在复盘',reserved:'正在安排复盘',waiting:'待你回复',no_progress:'复盘待调整',blocked:'复盘需处理',failed:'复盘需处理',cancelled:'复盘已停止',interrupted:'复盘已停止'} as Record<string,string>)[mission.organizerState||'']||'等待任务结果复盘'
  if(mission.state==='delivered')return mission.planConcluded===false?'等待任务结果复盘':mission.planConcluded===true&&mission.allTasksVerified?'成果可用':'待核对交付状态'
  return missionLabels[mission.state]||'状态待确认'
}
