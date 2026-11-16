import {useState} from 'react'
import type {GoalMode,GoalControl} from './goalMode'

export default function GoalControls({goal,objective,disabled,onControl}:{goal?:GoalMode;
  objective:string;disabled:boolean;onControl:(kind:GoalControl,payload:Record<string,string|number>)=>void}){
  const [budget,setBudget]=useState(8)
  const [revised,setRevised]=useState(objective)
  const [deadline,setDeadline]=useState(()=>new Date(Date.now()+3600000).toISOString().slice(0,16))
  const states:Record<string,string>={ready:'等待执行',running:'执行中',waiting:'等待输入',paused:'已暂停',completed:'已完成',failed:'执行失败',cancelled:'已取消'}
  const reasons:Record<string,string>={user_pause:'用户暂停',objective_revised:'目标已修改，请恢复执行',attempt_budget_exhausted:'已达到执行次数上限',deadline_elapsed:'已到截止时间',goal_receipt_missing:'缺少有效进度回执',attempt_interrupted:'执行中断，需要检查后恢复'}
  return <section aria-label="持续目标">
    {goal?<>
      <p role="status">持续目标：{states[goal.state]} · 已执行 {goal.attempts_admitted}/{goal.max_attempts} 次</p>
      <p>{goal.objective}</p>
      {goal.reason&&<p>{reasons[goal.reason]||goal.reason}</p>}
      {!['completed','failed','cancelled'].includes(goal.state)&&<>
        <label>修改目标<input value={revised} onChange={e=>setRevised(e.target.value)}/></label>
        <button disabled={disabled||!revised.trim()||revised===goal.objective} onClick={()=>onControl('revise_goal_objective',{objective:revised})}>保存目标修改</button>
      </>}
      {['ready','running'].includes(goal.state)&&<button disabled={disabled} onClick={()=>onControl('pause_goal',{})}>暂停目标</button>}
      {['paused','waiting'].includes(goal.state)&&<button disabled={disabled} onClick={()=>onControl('resume_goal',{})}>恢复目标</button>}
      {!['completed','failed','cancelled'].includes(goal.state)&&<button disabled={disabled} onClick={()=>onControl('cancel_goal',{})}>取消目标</button>}
    </>:<>
      <label>最多执行次数<input type="number" min={1} value={budget} onChange={e=>setBudget(Number(e.target.value))}/></label>
      <label>截止时间（UTC）<input type="datetime-local" value={deadline} onChange={e=>setDeadline(e.target.value)}/></label>
      <button disabled={disabled||!objective.trim()||!Number.isSafeInteger(budget)||budget<1||!Number.isFinite(Date.parse(deadline+'Z'))}
        onClick={()=>onControl('start_goal',{objective,max_attempts:budget,deadline_at:new Date(deadline+'Z').toISOString()})}>启用持续目标</button>
    </>}
  </section>
}
