import {expect,it} from 'vitest'
import {missionObjectiveFromInput,parseMission,parseMissionRefs,missionStateLabel} from './missions'
it('recognizes only the explicit Mission entry and preserves rough intent',()=>{
  expect(missionObjectiveFromInput('/mission 帮我准备研究')).toBe('帮我准备研究')
  expect(missionObjectiveFromInput('讨论 /mission')).toBeNull()
  expect(missionObjectiveFromInput('/missions')).toBeNull()
  expect(missionObjectiveFromInput('/goal 研究')).toBeNull()
})
it('keeps Mission aggregate identity and validates the owning Thread',()=>{
  const row={schema:'capstone-control-mission/1',mission_id:'goal_one',goal_id:'goal_one',workspace:'enterprise',objective:'研究',state:'planning',revision:1,origin:{thread_id:'thr_one'},plan_complete:false}
  expect(parseMission(row,'enterprise','thr_one').missionId).toBe('goal_one')
  expect(()=>parseMission({...row,origin:{thread_id:'thr_other'}},'enterprise','thr_one')).toThrow()
  expect(()=>parseMission({...row,mission_id:'goal_other'},'enterprise','thr_one')).toThrow()
  expect(parseMissionRefs([{mission_id:'goal_one'}])).toEqual([{missionId:'goal_one'}])
})
it('distinguishes a review boundary from a concluded and verified delivery',()=>{
 const row={schema:'capstone-control-mission/1',mission_id:'goal_one',goal_id:'goal_one',workspace:'enterprise',objective:'研究',state:'delivered',revision:1,origin:{thread_id:'thr_one'},plan_complete:true,plan_revision:2,acceptance_criteria:['Saved'],tasks:[{task_id:'task_one',state:'verified',delivery:{revision:1,answer_ref:'answer_one',products:[]},verification:{delivery_revision:1}}]}
 expect(missionStateLabel(parseMission({...row,plan_concluded:false},'enterprise','thr_one'))).toBe('等待任务结果复盘')
 const typed={plan_revision:2,summary:'Observed saved answer',criteria_verdicts:[{criterion_index:0,status:'met',explanation:'Read the current answer',evidence:[{kind:'answer',task_id:'task_one',answer_ref:'answer_one'}]}]}
 expect(missionStateLabel(parseMission({...row,plan_concluded:true,plan_conclusion:typed},'enterprise','thr_one'))).toBe('成果可用')
 expect(missionStateLabel(parseMission({...row,plan_concluded:true},'enterprise','thr_one'))).toBe('原计划结论待核验')
 expect(missionStateLabel(parseMission({...row,plan_concluded:true,plan_conclusion:typed,tasks:[{state:'delivered'}]},'enterprise','thr_one'))).toBe('仍有未完成事项')
 expect(missionStateLabel(parseMission({...row,reason:'partial_delivery'},'enterprise','thr_one'))).toBe('部分交付')
 expect(missionStateLabel(parseMission({...row,state:'waiting',reason:'acceptance_incomplete'},'enterprise','thr_one'))).toBe('仍有未完成事项')
 expect(missionStateLabel(parseMission({...row,state:'waiting_review'},'enterprise','thr_one'))).toBe('等待任务结果复盘')
 expect(missionStateLabel(parseMission({...row,state:'waiting_review',organizer:{state:'running'}},'enterprise','thr_one'))).toBe('正在复盘')
})
