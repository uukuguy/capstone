import {useEffect,useState} from 'react'
import type {HttpThreadTransport} from './threadHttpTransport'
import {missionStateLabel,type Mission} from './missions'
import type {NativeArtifact} from './nativeArtifacts'
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
}

export default function MissionStatus({transport,threadId,missionId,onCopyHandoff}:{
  transport:HttpThreadTransport;threadId:string;missionId:string;onCopyHandoff?:(id:string,revision:number)=>void
}){
  const [mission,setMission]=useState<Mission>(),[error,setError]=useState('')
  const [download,setDownload]=useState<string>(),[downloadError,setDownloadError]=useState('')
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
  useEffect(()=>{
    let active=true
    const read=()=>void transport.mission(missionId,threadId).then(row=>{if(active){setMission(row);setError('')}}).catch(()=>{if(active)setError('Mission 状态暂不可用')})
    setMission(undefined);read();const timer=window.setInterval(read,4000)
    return()=>{active=false;window.clearInterval(timer)}
  },[transport,threadId,missionId])
  const tasks=mission?.tasks||[]
  const taskPositions=new Map(tasks.map((task,index)=>[task.id,index+1]))
  const taskGaps=new Map(mission?.openItems?.map(item=>[item.taskId,item.reason]))
  const openItems=mission?.openItems?.filter(item=>item.kind!=='organizer'&&!taskPositions.has(item.taskId||''))||[]
  return <details className="mission-status">
    <summary>Mission · {error||(!mission?'正在读取':missionStateLabel(mission))}</summary>
    <div className="mission-status-body" tabIndex={0}>
    <p>{mission?.objective||missionId}</p>
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
        {criterion.products?.map(file=><button key={file.artifact_id} type="button" className="thread-control-button"
          disabled={!!download} onClick={()=>void saveProduct(file)}>
          {download===file.artifact_id?'正在核验并下载':`下载 ${file.file_name}`}
        </button>)}
      </li>)}</ul>
      {downloadError && <p role="alert">{downloadError}</p>}
    </section>}
    {mission && onCopyHandoff && <button type="button" className="thread-control-button"
      onClick={() => onCopyHandoff(mission.missionId,mission.revision)}>复制 Mission 续作引用</button>}
    </div>
  </details>
}
