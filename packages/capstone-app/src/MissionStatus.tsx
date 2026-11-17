import {useEffect,useState} from 'react'
import type {HttpThreadTransport} from './threadHttpTransport'
import {missionStateLabel,type Mission} from './missions'
import './missionStatus.css'
export default function MissionStatus({transport,threadId,missionId}:{transport:HttpThreadTransport;threadId:string;missionId:string}){
  const [mission,setMission]=useState<Mission>(),[error,setError]=useState('')
  useEffect(()=>{
    let active=true
    const read=()=>void transport.mission(missionId,threadId).then(row=>{if(active){setMission(row);setError('')}}).catch(()=>{if(active)setError('Mission 状态暂不可用')})
    setMission(undefined);read();const timer=window.setInterval(read,4000)
    return()=>{active=false;window.clearInterval(timer)}
  },[transport,threadId,missionId])
  return <details className="mission-status"><summary>Mission · {error||(!mission?'正在读取':missionStateLabel(mission))}</summary><p>{mission?.objective||missionId}</p><small>当前会话的 Mission。继续在对话中调整目标、条件和任务安排。</small></details>
}
