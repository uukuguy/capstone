import {applicationCapacity,exceedsCapacity,rethrowDebugCapacity} from './applicationCapacity'
import type {EventEnvelope} from './threadProtocol'
/** Public instruction-file identities. These are not task-level deliveries. */
export type NativeArtifact={
  schema:'capstone-process-artifact/1';scope:'instruction'
  thread_id:string;run_id:string;turn_id:string;attempt_id:string;work_id:string|null
  task_snapshot_id:string|null;goal_revision:number|null;task_id:string;artifact_id:string
  executor_identity_sha256:string;source_status:string;file_name:string;media_type:string
  producer_attempt_id?:string;host_artifact_id?:string
  presentation_role?:'primary'|'support'|'reproduction'
  delivery_status?:'limited'|'completed';delivery_limitations?:string[]
  sha256:string;size_bytes:number;download_url:string
}
export type NativeArtifactPage={artifacts:NativeArtifact[];hasMore:boolean;nextAfter:number}
export const MAX_NATIVE_ARTIFACT_BYTES=applicationCapacity('artifact_file_bytes')
const id=/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/
const hash=/^[a-f0-9]{64}$/
const media=new Set(['text/markdown','text/plain','text/csv','text/html','image/svg+xml','application/json','application/pdf','image/png','image/jpeg','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','application/octet-stream'])
function record(value:unknown):Record<string,unknown>{
  if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('指令文件信息无效')
  return value as Record<string,unknown>
}
function identity(value:unknown):value is string{return typeof value==='string'&&id.test(value)}
export function parseNativeArtifact(value:unknown,threadId:string,attemptId:string):NativeArtifact {
  const item=record(value)
  if(item.presentation_role!==undefined&&!['primary','support','reproduction'].includes(String(item.presentation_role)))throw new Error('成果用途无效')
  if(item.delivery_status!==undefined&&!['limited','completed'].includes(String(item.delivery_status)))throw new Error('交付状态无效')
  if(item.delivery_limitations!==undefined&&(!Array.isArray(item.delivery_limitations)||exceedsCapacity(item.delivery_limitations.length,'ui_delivery_support_count')
    ||!item.delivery_limitations.every(value=>typeof value==='string'&&value.trim())
    ||exceedsCapacity(item.delivery_limitations.reduce((sum:number,value:string)=>sum+value.length,0),'ui_delivery_scope_chars')))throw new Error('交付限制无效')
  if(item.schema!=='capstone-process-artifact/1'||item.scope!=='instruction'||item.thread_id!==threadId||item.attempt_id!==attemptId
    || ![item.thread_id,item.run_id,item.turn_id,item.attempt_id,item.task_id].every(identity)
    || !(item.work_id===null||identity(item.work_id))||!(item.task_snapshot_id===null||identity(item.task_snapshot_id))
    || !(item.goal_revision===null||Number.isSafeInteger(item.goal_revision)&&(item.goal_revision as number)>=1)
    || (item.work_id===null)!==(item.task_snapshot_id===null)||(item.work_id===null)!==(item.goal_revision===null)
    || typeof item.artifact_id!=='string'||!/^file-[a-f0-9]{16}-[a-f0-9]{64}$/.test(item.artifact_id)
    || typeof item.sha256!=='string'||!hash.test(item.sha256)||!item.artifact_id.endsWith(`-${item.sha256}`)
    || typeof item.executor_identity_sha256!=='string'||!hash.test(item.executor_identity_sha256)
    || (item.producer_attempt_id!==undefined&&!identity(item.producer_attempt_id))
    || (item.host_artifact_id!==undefined&&(!identity(item.host_artifact_id)||!item.host_artifact_id.endsWith(`-${item.sha256}`)))
    || typeof item.source_status!=='string'||!/^[a-z][a-z0-9_-]{0,63}$/.test(item.source_status)
    || typeof item.file_name!=='string'||!item.file_name||item.file_name==='.'||item.file_name==='..'||/[\\/\u0000-\u001f\u007f]/.test(item.file_name)||new TextEncoder().encode(item.file_name).byteLength>255
    || typeof item.media_type!=='string'||!media.has(item.media_type)
    || !Number.isSafeInteger(item.size_bytes)||(item.size_bytes as number)<0||exceedsCapacity(item.size_bytes as number,'artifact_file_bytes')
    || item.download_url!==`/api/v1/threads/${encodeURIComponent(threadId)}/attempts/${encodeURIComponent(attemptId)}/artifacts/${encodeURIComponent(item.artifact_id)}`)throw new Error('指令文件归属或内容信息无效')
  return {...item} as NativeArtifact
}
export function parseNativeArtifacts(value:unknown,threadId:string,attemptId:string,after=0):NativeArtifactPage {
  const page=record(value)
  if(!identity(threadId)||!identity(attemptId)||!Number.isSafeInteger(after)||after<0||page.schema!=='capstone-process-artifacts/1'
    ||page.thread_id!==threadId||page.attempt_id!==attemptId||!Array.isArray(page.artifacts)||exceedsCapacity(page.artifacts.length,'artifact_page_items')
    ||typeof page.has_more!=='boolean'||!Number.isSafeInteger(page.next_after)||(page.next_after as number)<after
    ||page.has_more&&(page.next_after as number)<=after)throw new Error('指令文件目录无效')
  const artifacts=page.artifacts.map(item=>parseNativeArtifact(item,threadId,attemptId))
  if(new Set(artifacts.map(item=>item.artifact_id)).size!==artifacts.length)throw new Error('指令文件身份重复')
  return {artifacts,hasMore:page.has_more,nextAfter:page.next_after as number}
}
export function projectNativeArtifacts(events:readonly EventEnvelope[]):NativeArtifact[] {
  const files=new Map<string,NativeArtifact>()
  for(const event of events){
    if(event.visibility!=='public'||event.eventType!=='native_artifact_published'||!event.attemptId)continue
    try{
      const artifact=parseNativeArtifact(event.payload.artifact,event.threadId,event.attemptId)
      if(artifact.run_id!==event.runId||artifact.turn_id!==event.turnId)continue
      files.set(`${artifact.attempt_id}:${artifact.artifact_id}`,artifact)
    }catch(error){rethrowDebugCapacity(error) /* Invalid or unowned descriptors cannot become file actions. */}
  }
  return [...files.values()]
}

export function groupNativeArtifacts(files:readonly NativeArtifact[]) {
  return {
    primary:files.filter(file=>file.presentation_role==='primary'),
    support:files.filter(file=>file.presentation_role==='support'),
    reproduction:files.filter(file=>file.presentation_role==='reproduction'),
    other:files.filter(file=>!file.presentation_role),
  }
}
