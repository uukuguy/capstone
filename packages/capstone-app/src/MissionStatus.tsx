import {useEffect,useRef,useState} from 'react'
import {ThreadTransportError,type HttpThreadTransport} from './threadHttpTransport'
import {missionStateLabel,type Mission} from './missions'
import type {NativeArtifact} from './nativeArtifacts'
import ObjectiveDeliveryDownload from './ObjectiveDeliveryDownload'
import './missionStatus.css'
const taskLabels:Record<string,string> = {
  pending:'待执行', delegated:'已安排', running:'执行中', awaiting_verification:'待核对',
  dispatching:'正在派发', verified:'已核对', delivered:'已交付，待核对', blocked:'暂时受阻', failed:'执行失败', cancelled:'已停止',
}
const executionLabels={direct:'主会话直办',single:'子会话 Instruction',goal:'子会话 Goal'}
const criterionLabels={met:'已满足',not_met:'未满足',unknown:'待核实'}
const reasonLabels:Record<string,string>={
  child_goal_partial_delivery:'子目标仅交付了部分成果',
  required_product_missing:'缺少所需产物',
  task_admission_unavailable:'任务执行能力暂不可用，系统会重新检查',
  equipment_admission_unavailable:'任务所需的注册资源暂不可用，系统会重新检查',
  equipment_excluded_during_planning:'任务选择的技能超出本轮规划范围，需要调整任务',
  delivery_verification_unavailable:'已保存交付，核验暂不可用',
}

export function useMissionProgress(transport:HttpThreadTransport,threadId:string,missionId?:string) {
  const key=missionId&&`${threadId}:${missionId}`
  const [state,setState]=useState<{key:string;mission?:Mission;error?:string}>()
  useEffect(()=>{
    if(!missionId||!key)return
    let active=true
    const read=()=>void transport.mission(missionId,threadId)
      .then(mission=>{if(active)setState(previous=>previous?.key===key&&(previous.mission?.revision||0)>mission.revision?previous:{key,mission})})
      .catch(()=>{if(active)setState(previous=>({key,mission:previous?.key===key?previous.mission:undefined,error:'状态暂不可用'}))})
    read()
    const timer=window.setInterval(read,4000)
    return()=>{active=false;window.clearInterval(timer)}
  },[transport,threadId,missionId,key])
  const mission=state?.key===key?state?.mission:undefined
  const error=state?.key===key?state?.error:undefined
  return {mission,label:error||(mission?missionStateLabel(mission):'正在读取'),
    apply:(mission:Mission)=>{if(key)setState(previous=>previous?.key===key&&(previous.mission?.revision||0)>mission.revision?previous:{key,mission})}}
}

export default function MissionStatus({transport,missionId,progress,onCopyHandoff}:{
  transport:HttpThreadTransport;missionId:string;progress:ReturnType<typeof useMissionProgress>;
  onCopyHandoff?:(id:string,revision:number)=>void
}){
  const {mission,label}=progress
  const [download,setDownload]=useState<string>(),[downloadError,setDownloadError]=useState('')
  const [resuming,setResuming]=useState(false),[resumeError,setResumeError]=useState('')
  const resumeRequest=useRef<{revision:number;operationId:string}|undefined>(undefined)
  async function resume() {
    if(!mission||resuming)return
    if(resumeRequest.current?.revision!==mission.revision)
      resumeRequest.current={revision:mission.revision,operationId:'op_'+crypto.randomUUID().replaceAll('-','')}
    setResuming(true)
    setResumeError('')
    try{
      const send=(request:{revision:number;operationId:string})=>transport.resumeMission(
        missionId,mission.origin.thread_id,request.revision,request.operationId)
      try{
        progress.apply(await send(resumeRequest.current))
      }catch(error){
        if(!(error instanceof ThreadTransportError)||error.status!==409
          ||!error.body||typeof error.body!=='object'||!('detail' in error.body)
          ||error.body.detail!=='stale Mission revision')throw error
        const latest=await transport.mission(missionId,mission.origin.thread_id)
        progress.apply(latest)
        if(latest.state!=='delivered'||latest.reason!=='partial_delivery')return
        if(mission.planRevision===undefined||latest.planRevision!==mission.planRevision||latest.revision<=mission.revision
          ||latest.conclusionSummary!==mission.conclusionSummary
          ||JSON.stringify(latest.criteria)!==JSON.stringify(mission.criteria)){
          setResumeError('Mission 的计划或交付已更新，请核对当前内容。')
          return
        }
        resumeRequest.current={revision:latest.revision,operationId:'op_'+crypto.randomUUID().replaceAll('-','')}
        progress.apply(await send(resumeRequest.current))
      }
      resumeRequest.current=undefined
    }catch(error){
      setResumeError(error instanceof Error?error.message:'Mission 恢复请求未确认，可重试。')
    }finally{
      setResuming(false)
    }
  }
  async function saveProduct(file:NativeArtifact){
    setDownload(file.artifact_id)
    setDownloadError('')
    try{
      const bytes=await transport.readNativeArtifact(file)
      const url=URL.createObjectURL(new Blob([new Uint8Array(bytes)],{type:file.media_type}))
      const link=document.createElement('a')
      link.href=url
      link.download=file.file_name
      link.click()
      setTimeout(()=>URL.revokeObjectURL(url),1000)
    }catch{
      setDownloadError(`无法下载 ${file.file_name}。请重试。`)
    }finally{
      setDownload(undefined)
    }
  }
  const tasks=mission?.tasks||[]
  const taskPositions=new Map(tasks.map((task,index)=>[task.id,index+1]))
  const taskGaps=new Map(mission?.openItems?.map(item=>[item.taskId,item.reason]))
  const openItems=mission?.openItems?.filter(item=>item.kind!=='organizer'&&!taskPositions.has(item.taskId||''))||[]
  const verifiedProducts=[...new Map(mission?.criteria?.flatMap(criterion=>
    (criterion.products||[]).map(file=>[file.artifact_id,file] as const))).values()]
  return <details className="mission-status" open>
    <summary>Mission · {label}</summary>
    <div className="mission-status-body" tabIndex={0}>
    <p>{mission?.objective||missionId}</p>
    {mission?.state==='delivered'&&mission.reason==='partial_delivery'&&
      <button type="button" className="thread-control-button" disabled={resuming} onClick={()=>void resume()}>
        {resuming?'正在恢复 Mission':'继续 Mission'}
      </button>}
    {resumeError&&<p role="alert">{resumeError}</p>}
    {mission?.conclusionSummary&&<section aria-label="Mission 整体交付">
      <h3>Mission 整体交付</h3>
      <p>{mission.conclusionSummary}</p>
      {(mission.planConcluded||mission.state==='delivered'&&mission.reason==='partial_delivery')&&<ObjectiveDeliveryDownload fileName={`mission-delivery-v${mission.revision}.md`} delivery={{
        title:'Mission 整体交付', objective:mission.objective, revision:mission.revision,
        status:label, summary:mission.conclusionSummary,
        criteria:(mission.criteria||[]).map(criterion=>({label:criterion.label,status:criterionLabels[criterion.status||'unknown'],
          explanation:criterion.explanation,
          references:criterion.products?.map(file=>`${file.file_name} · SHA-256 ${file.sha256}`)})),
      }}/>}
    </section>}
    {tasks.length>0 && <ol aria-label="Mission 执行计划">{tasks.map(task=>{
      const dependencies=task.dependencies.map(id=>taskPositions.get(id)).filter(position=>position!==undefined)
      const reason=reasonLabels[taskGaps.get(task.id)||'']
      return <li key={task.id}>
        <p>{task.objective}</p>
        <small>{executionLabels[task.execution]} · {taskLabels[task.state] || '待处理'}</small>
        {task.revision>1 && <small>任务要求已调整 · 第 {task.revision} 版</small>}
        {dependencies.length>0 && <small>依赖第 {dependencies.join('、')} 项</small>}
        {reason && <small>{reason}</small>}
      </li>
    })}</ol>}
    {openItems.length>0 && <ul aria-label="Mission 未完成事项">{openItems.map((item,index) =>
      <li key={index}>{item.kind === 'mission_plan_incomplete' ? '计划尚未完整' :
        `${taskLabels[item.state || ''] || '待处理'} · ${item.objective || '子任务'}`}</li>)}</ul>}
    {!!mission?.criteria?.length && <section aria-label="Mission 完成条件">
      <p>完成条件</p>
      <ul>{mission.criteria.map((criterion,index)=><li key={index}>
        <p>{criterion.label} · {criterionLabels[criterion.status||'unknown']}</p>
        {criterion.explanation && <small>{criterion.explanation}</small>}
      </li>)}</ul>
    </section>}
    {verifiedProducts.length>0&&<section aria-label="已核验成果">
      <p>已核验成果</p>
      <div className="mission-product-actions">{verifiedProducts.map(file=><button key={file.artifact_id} type="button"
        className="thread-control-button" disabled={!!download} onClick={()=>void saveProduct(file)}>
        {download===file.artifact_id?'正在核验并下载':`下载 ${file.file_name}`}
      </button>)}</div>
      {downloadError&&<p role="alert">{downloadError}</p>}
    </section>}
    {mission && onCopyHandoff && <button type="button" className="thread-control-button"
      onClick={() => onCopyHandoff(mission.missionId,mission.revision)}>复制 Mission 续作引用</button>}
    </div>
  </details>
}
