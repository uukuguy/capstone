import {useEffect,useState} from 'react'
import type {HttpThreadTransport} from './threadHttpTransport'
import {missionStateLabel,type Mission} from './missions'
import './missionStatus.css'
const taskLabels:Record<string,string> = {
  pending:'待执行', delegated:'已安排', running:'执行中', awaiting_verification:'待核对',
  dispatching:'正在派发', verified:'已核对', delivered:'已交付，待核对', blocked:'暂时受阻', failed:'执行失败', cancelled:'已停止',
}

export default function MissionStatus({transport,threadId,missionId,onCopyHandoff}:{
  transport:HttpThreadTransport;threadId:string;missionId:string;onCopyHandoff?:(id:string,revision:number)=>void
}){
  const [mission,setMission]=useState<Mission>(),[error,setError]=useState('')
  useEffect(()=>{
    let active=true
    const read=()=>void transport.mission(missionId,threadId).then(row=>{if(active){setMission(row);setError('')}}).catch(()=>{if(active)setError('Mission 状态暂不可用')})
    setMission(undefined);read();const timer=window.setInterval(read,4000)
    return()=>{active=false;window.clearInterval(timer)}
  },[transport,threadId,missionId])
  const openItems = mission?.openItems?.filter(item => item.kind !== 'organizer' && (item.kind !== 'mission_task' || !mission.tasks?.length)) || []
  return <details className="mission-status">
    <summary>Mission · {error||(!mission?'正在读取':missionStateLabel(mission))}</summary>
    <p>{mission?.objective||missionId}</p>
    {!!mission?.tasks?.length && <ul aria-label="Mission 执行计划">{mission.tasks.map(task =>
      <li key={task.id}>{task.objective} · {{direct:'主会话直办',single:'子会话 Instruction',goal:'子会话 Goal'}[task.execution]}
        {' · '}{taskLabels[task.state] || '待处理'}</li>)}</ul>}
    {openItems.length>0 && <ul aria-label="Mission 未完成事项">{openItems.map((item,index) =>
      <li key={index}>{item.kind === 'mission_plan_incomplete' ? '计划尚未完整' :
        `${taskLabels[item.state || ''] || '待处理'} · ${item.objective || '子任务'}`}</li>)}</ul>}
    {mission && onCopyHandoff && <button type="button" className="thread-control-button"
      onClick={() => onCopyHandoff(mission.missionId,mission.revision)}>复制 Mission 续作引用</button>}
  </details>
}
