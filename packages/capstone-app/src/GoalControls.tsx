import {useState} from 'react'
import type {GoalMode,GoalControl} from './goalMode'
import type {SessionGoalPlan} from './threadWorkProtocol'
import './GoalControls.css'

export default function GoalControls({goal,plan,planning,objective,disabled,executing,onControl,placement}:{goal?:GoalMode; plan?:SessionGoalPlan; planning?:boolean; executing?:boolean;placement?:'summary'|'details';
  objective:string;disabled:boolean;onControl:(kind:GoalControl,payload:Record<string,string|number>)=>void}){
  const [budget,setBudget]=useState(8)
  const [revised,setRevised]=useState(objective)
  const [deadline,setDeadline]=useState('')
  const defaultDeadline=()=>new Date(Date.now()+3600000)
  const reviewRetry=goal?.state==='paused'&&goal.reason?.startsWith('goal_review_')
  const resumeLimit=goal&&!reviewRetry&&(goal.attempts_admitted>=goal.max_attempts?'原目标已用完执行次数。':Date.parse(goal.deadline_at)<=Date.now()?'原目标已到截止时间。':undefined)
  const canSendFollowup=goal&&['paused','waiting','completed','failed','cancelled'].includes(goal.state)&&goal.reason!=='goal_review_pending'
  const states:Record<string,string>={ready:'等待执行',running:'执行中',waiting:'等待结果',paused:'已暂停',completed:'已完成',failed:'执行失败',cancelled:'已取消'}
  const verdicts={met:'已满足',unmet:'未满足',unknown:'待核实'}
  const stateLabel=goal&&(planning&&goal.state==='ready'?'正在规划':goal.reason==='goal_review_pending'?'正在复盘':goal.reason==='partial_delivery'?'部分完成':states[goal.state])
  const criteriaOpen=plan?.criterionVerdicts&&Object.values(plan.criterionVerdicts).filter(verdict=>verdict!=='met').length
  const progressLabel=plan&&goal&&(
    (['ready','running','waiting','paused'].includes(goal.state)&&!planning)
      ? ` · 第 ${plan.stepIndex+1}/${plan.steps.length} 步`
      : goal.state==='completed'&&criteriaOpen
        ? ` · ${criteriaOpen} 项完成条件未满足或待核实`
        : '')
  const actions=goal&&<>
    {(['ready','running'].includes(goal.state)||goal.reason==='goal_review_pending')&&<button type="button" className="thread-control-button" disabled={disabled} onClick={()=>onControl('pause_goal',{})}>暂停目标</button>}
    {['paused','waiting'].includes(goal.state)&&goal.reason!=='goal_review_pending'&&!resumeLimit&&<button type="button" className="thread-control-button" disabled={disabled||executing} onClick={()=>onControl('resume_goal',{})}>{reviewRetry?'重新复盘已保存成果':'继续原目标'}</button>}
  </>
  if(placement==='summary'&&goal)return <>
    <span role="status" title={`已执行 ${goal.attempts_admitted} 次，上限 ${goal.max_attempts} 次`}>Goal · {stateLabel}{progressLabel}</span>
    {actions}
  </>
  const reasons:Record<string,string>={user_pause:'用户暂停',objective_revised:'目标已修改，请恢复执行',attempt_budget_exhausted:'已达到执行次数上限',deadline_elapsed:'已到截止时间',goal_planning_failed:'目标规划失败，可恢复后重新规划',goal_review_pending:'本步成果已保存，正在复盘',goal_review_invalid:'复盘结果未通过校验。已保存的回复和制品仍可查看。',goal_receipt_missing:'缺少有效进度回执',attempt_interrupted:'执行中断，需要检查后恢复',attempt_failed:'本次执行失败，可检查已有成果后恢复',attempt_cancelled:'执行已停止'}
  const reviewReasons:Record<string,string>={
    goal_review_unavailable:'复盘暂不可用。已保存成果，可以重新复盘。',
    goal_review_reference_unavailable:'复盘引用了无法核对的制品或证据。',
    goal_review_next_step_invalid:'复盘提出的下一步与保存的计划不匹配。',
    goal_review_criteria_incomplete:'复盘还没有逐项核实全部完成条件。',
    goal_review_criterion_unverified:'至少有一项完成条件缺少可核对的证据。',
  }
  const continuationReasons:Record<string,string>={
    goal_continuation_product_context_unavailable:'部分成果暂时无法绑定。',
    goal_continuation_authority_input_unavailable:'本步所需的来源暂时无法核对。',
    goal_continuation_worker_unavailable:'本步所需的执行器暂不可用。',
  }
  return <section className="goal-controls" aria-label="持续目标">
    {goal?<>
      <p role={placement==='details'?undefined:'status'}>Goal · {stateLabel} · {goal.attempts_admitted}/{goal.max_attempts} 次</p>
      <p>{goal.objective}</p>
      {goal.objective_revision>1 && <p>显示调整后的目标 · 第 {goal.objective_revision} 版</p>}
      {plan&&<details className="goal-plan" open={placement==='details'||undefined}>
        <summary>目标计划 · 第 {plan.stepIndex+1}/{plan.steps.length} 步</summary>
        <div className="goal-plan-body" tabIndex={0}>
          <ol>{plan.steps.map((step,index)=><li key={step.instruction} aria-current={index===plan.stepIndex?'step':undefined}>
            {step.instruction}{plan.unavailableSteps?.includes(index)&&<strong> · 未完成</strong>}<p>预期成果：{step.expectedResult}</p>
          </li>)}</ol>
          <p>完成条件</p>
          <ul>{plan.criteria.map((criterion,index)=>{
            const verdict=plan.criterionVerdicts?.[index]
            return <li key={index}>{criterion}{verdict&&<> · {verdicts[verdict]}</>}</li>
          })}</ul>
        </div>
      </details>}
      {goal.state==='completed'&&plan?.closureSummary&&<section aria-label="目标交付"><h3>目标交付</h3><p>{plan.closureSummary}</p></section>}
      {goal.reason&&goal.reason!=='goal_review_pending'&&goal.reason!=='partial_delivery'&&<p>{reviewReasons[goal.reason]||reasons[goal.reason]||
        (goal.reason.startsWith('goal_continuation_')?`下一步已保留。${continuationReasons[goal.reason]||'执行条件尚未满足。'}`:goal.reason)}</p>}
      {canSendFollowup&&<p>要继续其他工作，可直接在消息框发送新指令。</p>}
      {!['completed','failed','cancelled'].includes(goal.state)&&<details className="goal-settings">
        <summary>修改或结束目标</summary>
        <label>修改目标<input value={revised} onChange={e=>setRevised(e.target.value)}/></label>
        <button disabled={disabled||!revised.trim()||revised===goal.objective} onClick={()=>onControl('revise_goal_objective',{objective:revised})}>保存目标修改</button>
        <button disabled={disabled} onClick={()=>onControl('cancel_goal',{})}>取消目标</button>
      </details>}
      {['paused','waiting'].includes(goal.state)&&goal.reason!=='goal_review_pending'&&resumeLimit&&<p>{resumeLimit}</p>}
      {placement!=='details'&&actions}
    </>:<>
      <button disabled={disabled||!objective.trim()||!Number.isSafeInteger(budget)||budget<1||(deadline!==''&&!Number.isFinite(Date.parse(deadline+'Z')))}
        onClick={()=>onControl('start_goal',{objective,max_attempts:budget,deadline_at:(deadline?new Date(deadline+'Z'):defaultDeadline()).toISOString()})}>开始规划目标</button>
      <details className="goal-settings">
        <summary>执行设置</summary>
        <label>最多执行次数<input type="number" min={1} value={budget} onChange={e=>setBudget(Number(e.target.value))}/></label>
        <label>截止时间（UTC）<input type="datetime-local" value={deadline||defaultDeadline().toISOString().slice(0,16)} onChange={e=>setDeadline(e.target.value)}/></label>
      </details>
    </>}
  </section>
}
